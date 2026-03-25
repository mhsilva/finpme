"""
Router de upload de arquivos financeiros.
Suporta OFX, XML (NF-e) e CSV.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile, status

from db.supabase import get_supabase_client
from services.categorizer import categorizar_transacoes
from services.intelligent_parser import parse_com_ia
from services.parsers.csv_parser import parse_csv
from services.parsers.nfe_parser import parse_nfe_xml
from services.parsers.ofx_parser import parse_ofx

logger = logging.getLogger(__name__)
router = APIRouter()

# Parsers nativos (rápidos, sem custo de tokens)
PARSERS_NATIVOS = {"ofx", "xml", "csv"}
# Formatos que vão para o Claude (PDF, imagens)
TIPOS_IA = {"pdf", "png", "jpg", "jpeg", "webp"}
TIPOS_PERMITIDOS = PARSERS_NATIVOS | TIPOS_IA


def _extensao(filename: str) -> str:
    """Extrai extensão do arquivo em minúsculas."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def _salvar_contas_pr(client, tenant_id: str, file_id: str, notas: list):
    """Insere contas a pagar/receber geradas por NF-e ou parse IA."""
    registros = [
        {
            "tenant_id":    tenant_id,
            "type":         n["type"],
            "description":  n["description"],
            "amount":       float(n["amount"]),
            "due_date":     n["due_date"],
            "contact_name": n.get("contact_name"),
            "contact_doc":  n.get("contact_doc"),
            "notes":        n.get("notes"),
            "status":       "pending",
        }
        for n in notas
    ]
    if registros:
        client.table("payables_receivables").insert(registros).execute()


async def _salvar_transacoes(client, tenant_id: str, file_id: str, source: str, transacoes: list):
    """Insere transações bancárias categorizadas."""
    registros = [
        {
            "tenant_id":      tenant_id,
            "date":           t["date"],
            "description":    t["description"],
            "amount":         float(t["amount"]),
            "category":       t.get("category"),
            "subcategory":    t.get("subcategory"),
            "dre_line":       t.get("dre_line"),
            "source":         source,
            "source_file_id": file_id,
            "ai_categorized": True,
            "ai_confidence":  t.get("confidence"),
            "confirmed":      False,
        }
        for t in transacoes
    ]
    if registros:
        client.table("transactions").insert(registros).execute()


async def _processar_arquivo_em_background(
    file_id: str,
    tenant_id: str,
    file_type: str,
    storage_path: str,
):
    """
    Pipeline de processamento rodando em background:
    1. Baixa arquivo do Storage
    2. Parseia transações
    3. Categoriza com IA
    4. Salva no banco
    5. Atualiza status
    """
    client = get_supabase_client()
    logger.info(f"Iniciando processamento do arquivo {file_id} (tenant {tenant_id})")

    try:
        # Atualiza status para 'processing'
        client.table("uploaded_files").update({"status": "processing"}).eq("id", file_id).execute()

        # 1. Baixa do Storage
        conteudo = client.storage.from_("extratos").download(storage_path)

        # 2. Parseia conforme tipo e roteia para tabela correta
        if file_type == "xml":
            # NF-e → gera contas a pagar/receber, não lançamentos
            notas = parse_nfe_xml(conteudo)
            await _salvar_contas_pr(client, tenant_id, file_id, notas)
            client.table("uploaded_files").update({
                "status": "done",
                "processed_at": datetime.utcnow().isoformat(),
            }).eq("id", file_id).execute()
            logger.info(f"NF-e {file_id}: {len(notas)} conta(s) P/R gerada(s)")
            return

        if file_type in TIPOS_IA:
            # PDF / imagem → parse inteligente via Claude
            resultado = parse_com_ia(conteudo, file_type, storage_path.rsplit("/", 1)[-1])

            if resultado["tipo"] == "invalido":
                raise ValueError(f"Documento não reconhecido: {resultado.get('motivo')}")

            if resultado["tipo"] == "nota":
                await _salvar_contas_pr(client, tenant_id, file_id, [resultado["dados"]])
            else:
                # extrato → transações
                transacoes = resultado["dados"] or []
                transacoes_categorizadas = await categorizar_transacoes(transacoes, tenant_id)
                await _salvar_transacoes(client, tenant_id, file_id, file_type, transacoes_categorizadas)

            client.table("uploaded_files").update({
                "status": "done",
                "processed_at": datetime.utcnow().isoformat(),
            }).eq("id", file_id).execute()
            logger.info(f"Upload IA {file_id}: processado como '{resultado['tipo']}'")
            return

        # OFX / CSV → extrato bancário → gera lançamentos (transactions)
        if file_type == "ofx":
            transacoes = parse_ofx(conteudo)
        elif file_type == "csv":
            transacoes = parse_csv(conteudo)
        else:
            raise ValueError(f"Tipo de arquivo não suportado: {file_type}")

        logger.info(f"Arquivo {file_id}: {len(transacoes)} transações extraídas")

        # 3. Categoriza com IA (em lotes de 50)
        transacoes_categorizadas = await categorizar_transacoes(transacoes, tenant_id)

        # 4. Salva no banco
        await _salvar_transacoes(client, tenant_id, file_id, file_type, transacoes_categorizadas)

        # 5. Atualiza status para 'done'
        client.table("uploaded_files").update({
            "status": "done",
            "processed_at": datetime.utcnow().isoformat(),
        }).eq("id", file_id).execute()

        logger.info(f"Arquivo {file_id} processado: {len(transacoes_categorizadas)} lançamentos salvos")

    except Exception as e:
        logger.error(f"Erro ao processar arquivo {file_id}: {e}")
        client.table("uploaded_files").update({
            "status": "error",
            "processed_at": datetime.utcnow().isoformat(),
        }).eq("id", file_id).execute()


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def fazer_upload(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Recebe arquivo financeiro, salva no Supabase Storage e
    dispara processamento em background.
    """
    tenant_id: str = request.state.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não está vinculado a nenhuma empresa",
        )

    extensao = _extensao(file.filename or "")
    if extensao not in TIPOS_PERMITIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não suportado. Use: {', '.join(TIPOS_PERMITIDOS)}",
        )

    conteudo = await file.read()
    file_id = str(uuid.uuid4())
    storage_path = f"{tenant_id}/{file_id}.{extensao}"

    client = get_supabase_client()

    # Salva no Supabase Storage
    try:
        client.storage.from_("extratos").upload(
            path=storage_path,
            file=conteudo,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo no Storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao salvar arquivo",
        )

    # Cria registro no banco
    try:
        resultado = client.table("uploaded_files").insert({
            "id": file_id,
            "tenant_id": tenant_id,
            "filename": file.filename,
            "file_type": extensao,
            "storage_path": storage_path,
            "status": "pending",
        }).execute()
    except Exception as e:
        logger.error(f"Erro ao registrar arquivo no banco: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar arquivo",
        )

    # Dispara processamento em background
    background_tasks.add_task(
        _processar_arquivo_em_background,
        file_id=file_id,
        tenant_id=tenant_id,
        file_type=extensao,
        storage_path=storage_path,
    )

    logger.info(f"Upload recebido: {file.filename} → {file_id} (tenant {tenant_id})")
    return {
        "file_id": file_id,
        "filename": file.filename,
        "status": "pending",
        "message": "Arquivo recebido. O processamento começará em instantes.",
    }


@router.get("/status/{file_id}")
async def status_arquivo(file_id: str, request: Request):
    """Retorna o status de processamento de um arquivo enviado."""
    tenant_id: str = request.state.tenant_id
    client = get_supabase_client()

    resultado = (
        client.table("uploaded_files")
        .select("id, status, filename, processed_at, created_at")
        .eq("id", file_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )

    if not resultado.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado",
        )

    return resultado.data


@router.get("")
async def listar_uploads(request: Request):
    """Lista os arquivos enviados pelo tenant com seus status."""
    tenant_id: str = request.state.tenant_id
    client = get_supabase_client()

    resultado = (
        client.table("uploaded_files")
        .select("id, filename, file_type, status, processed_at, created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )

    return resultado.data or []
