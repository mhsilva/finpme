"""
Parser inteligente via Claude API.

Usado quando o arquivo não tem um parser nativo (PDF, imagem, planilha, etc.).
Usa tool_use para garantir JSON estruturado — sem parsing de texto livre.

Suporta dois tipos de retorno:
  - "extrato"  → lista de transactions (OFX/CSV convertido via IA)
  - "nota"     → payable ou receivable (NF-e, boleto, recibo)
  - "invalido" → arquivo não reconhecido como financeiro
"""

import base64
import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

MODELO = "claude-haiku-4-5-20251001"

# ── Tool schema: o que o Claude deve retornar ─────────────────────────────

TOOL_EXTRAIR = {
    "name": "extrair_dados_financeiros",
    "description": (
        "Extrai dados financeiros de um documento. "
        "Classifica o documento e retorna os dados estruturados."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "tipo_documento": {
                "type": "string",
                "enum": ["extrato_bancario", "nota_fiscal", "boleto", "recibo", "invalido"],
                "description": "Tipo do documento identificado",
            },
            "instituicao": {
                "type": "string",
                "description": "Nome do banco ou empresa emissora (se identificável)",
            },
            "transacoes": {
                "type": "array",
                "description": "Lista de transações (para extrato bancário)",
                "items": {
                    "type": "object",
                    "properties": {
                        "date":        {"type": "string", "description": "Data no formato YYYY-MM-DD"},
                        "description": {"type": "string", "description": "Descrição da transação"},
                        "amount":      {"type": "number",  "description": "Valor: positivo=entrada, negativo=saída"},
                    },
                    "required": ["date", "description", "amount"],
                },
            },
            "conta_pr": {
                "type": "object",
                "description": "Conta a pagar ou receber (para NF-e, boleto, recibo)",
                "properties": {
                    "type":         {"type": "string", "enum": ["payable", "receivable"]},
                    "description":  {"type": "string"},
                    "amount":       {"type": "number", "description": "Valor positivo"},
                    "due_date":     {"type": "string", "description": "Vencimento YYYY-MM-DD"},
                    "contact_name": {"type": "string"},
                    "contact_doc":  {"type": "string", "description": "CNPJ ou CPF"},
                    "notes":        {"type": "string"},
                },
                "required": ["type", "description", "amount", "due_date"],
            },
            "motivo_invalido": {
                "type": "string",
                "description": "Explicação quando tipo_documento = invalido",
            },
        },
        "required": ["tipo_documento"],
    },
}

PROMPT_SISTEMA = """Você é um especialista em documentos financeiros brasileiros.
Analise o documento fornecido e extraia os dados usando a ferramenta disponível.

Regras:
- Datas sempre em YYYY-MM-DD
- Valores numéricos sem formatação (ex: 1234.56, não "R$ 1.234,56")
- Para extratos: positivo = crédito/entrada, negativo = débito/saída
- Para NF-e/boleto: amount sempre positivo; defina type como payable (você deve pagar) ou receivable (vão te pagar)
- Se não conseguir identificar como documento financeiro, use tipo_documento = invalido
"""


def _media_type(extensao: str) -> str:
    return {
        "pdf":  "application/pdf",
        "png":  "image/png",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif":  "image/gif",
    }.get(extensao, "application/octet-stream")


def parse_com_ia(conteudo: bytes, extensao: str, nome_arquivo: str = "") -> dict[str, Any]:
    """
    Envia o arquivo para o Claude e retorna dados estruturados.

    Retorno:
      {
        "tipo": "extrato" | "nota" | "invalido",
        "dados": [ lista de transações ] OU { conta P/R } OU None,
        "motivo": str (quando invalido),
        "instituicao": str (quando extrato),
      }
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    conteudo_b64 = base64.standard_b64encode(conteudo).decode("utf-8")
    media = _media_type(extensao)

    # Monta o conteúdo da mensagem conforme tipo
    if extensao == "pdf":
        source_block = {
            "type":       "document",
            "source":     {"type": "base64", "media_type": media, "data": conteudo_b64},
        }
    else:
        # Imagem
        source_block = {
            "type":   "image",
            "source": {"type": "base64", "media_type": media, "data": conteudo_b64},
        }

    mensagem_usuario = f"Analise este arquivo financeiro ({nome_arquivo or extensao}) e extraia os dados."

    logger.info(f"Enviando {extensao} para parse inteligente via Claude ({len(conteudo)} bytes)")

    resposta = client.messages.create(
        model=MODELO,
        max_tokens=4096,
        system=PROMPT_SISTEMA,
        tools=[TOOL_EXTRAIR],
        tool_choice={"type": "any"},
        messages=[
            {
                "role": "user",
                "content": [source_block, {"type": "text", "text": mensagem_usuario}],
            }
        ],
    )

    # Extrai o resultado da tool_use
    resultado_tool = next(
        (b.input for b in resposta.content if b.type == "tool_use"),
        None,
    )
    if not resultado_tool:
        return {"tipo": "invalido", "dados": None, "motivo": "Claude não retornou dados estruturados"}

    tipo_doc = resultado_tool.get("tipo_documento", "invalido")

    if tipo_doc == "invalido":
        return {
            "tipo":   "invalido",
            "dados":  None,
            "motivo": resultado_tool.get("motivo_invalido", "Documento não reconhecido"),
        }

    if tipo_doc == "extrato_bancario":
        transacoes = resultado_tool.get("transacoes") or []
        logger.info(f"Parse IA: extrato com {len(transacoes)} transações")
        return {
            "tipo":        "extrato",
            "dados":       transacoes,
            "instituicao": resultado_tool.get("instituicao"),
        }

    # nota_fiscal | boleto | recibo → conta P/R
    conta = resultado_tool.get("conta_pr")
    if not conta:
        return {"tipo": "invalido", "dados": None, "motivo": "Documento P/R sem dados extraídos"}

    conta["source"] = "ia_upload"
    logger.info(f"Parse IA: {tipo_doc} → {conta.get('type')} R$ {conta.get('amount')}")
    return {
        "tipo":  "nota",
        "dados": conta,
    }
