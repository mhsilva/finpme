"""
Serviço de categorização de transações usando Claude API.
Categoriza lotes de até 50 transações por vez com retry e backoff.
"""

import asyncio
import json
import logging
import os
from typing import Any

import anthropic

from db.supabase import get_chart_of_accounts, get_supabase_client

logger = logging.getLogger(__name__)

MODELO_CLAUDE = "claude-haiku-4-5-20251001"
TAMANHO_LOTE = 50
TIMEOUT_ANTHROPIC = 30
MAX_TENTATIVAS = 3
BACKOFF_BASE = 2  # segundos

# Linhas válidas do DRE
LINHAS_DRE_VALIDAS = {
    "receita_bruta",
    "deducoes",
    "cmv",
    "despesa_vendas",
    "despesa_admin",
    "despesa_financeira",
    "outros",
}


def _formatar_plano_contas(contas: list[dict]) -> str:
    """Formata o plano de contas para incluir no prompt."""
    if not contas:
        return "Plano de contas padrão (use categorias genéricas de PME brasileira)"

    linhas = []
    for conta in contas[:30]:  # Limita para não explodir o prompt
        linha_dre = f" → DRE: {conta['dre_line']}" if conta.get("dre_line") else ""
        linhas.append(f"- {conta.get('code', '')} {conta['name']}{linha_dre}")

    return "\n".join(linhas)


def _extrair_json_resposta(texto: str) -> list[dict]:
    """
    Extrai o JSON da resposta do Claude.
    Tenta parse direto primeiro, depois procura bloco JSON no texto.
    """
    texto = texto.strip()

    # Tenta parse direto
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # Procura bloco JSON entre ```json e ```
    if "```json" in texto:
        inicio = texto.index("```json") + 7
        fim = texto.index("```", inicio)
        try:
            return json.loads(texto[inicio:fim].strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # Procura primeiro [ até último ]
    if "[" in texto and "]" in texto:
        inicio = texto.index("[")
        fim = texto.rindex("]") + 1
        try:
            return json.loads(texto[inicio:fim])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível extrair JSON válido da resposta: {texto[:200]}")


async def _categorizar_lote(
    cliente: anthropic.Anthropic,
    lote: list[dict],
    plano_contas: str,
    regime: str,
) -> list[dict]:
    """
    Envia um lote de transações para o Claude categorizar.
    Implementa retry com backoff exponencial.
    """
    transacoes_simplificadas = [
        {
            "id": t.get("id") or f"t_{i}",
            "date": t.get("date"),
            "description": t.get("description", ""),
            "amount": float(t.get("amount", 0)),
        }
        for i, t in enumerate(lote)
    ]

    prompt = f"""Você é um assistente contábil especializado em PMEs brasileiras.
Analise as transações abaixo e categorize cada uma conforme o plano de contas.

Regime fiscal da empresa: {regime}

Plano de contas disponível:
{plano_contas}

Linhas do DRE disponíveis: {', '.join(sorted(LINHAS_DRE_VALIDAS))}

Transações para categorizar:
{json.dumps(transacoes_simplificadas, ensure_ascii=False, indent=2)}

Responda SOMENTE em JSON, sem texto adicional, no formato:
[
  {{
    "id": "id_da_transacao",
    "category": "categoria do plano de contas",
    "subcategory": "subcategoria se aplicável",
    "dre_line": "linha_do_dre",
    "confidence": 0.95
  }}
]

Regras:
- dre_line deve ser EXATAMENTE uma das opções listadas
- confidence deve ser entre 0.0 e 1.0
- Para transações de entrada (amount > 0), use preferencialmente receita_bruta
- Para transferências e valores não identificados, use "outros"
- Responda em português"""

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = cliente.messages.create(
                model=MODELO_CLAUDE,
                max_tokens=4096,
                timeout=TIMEOUT_ANTHROPIC,
                messages=[{"role": "user", "content": prompt}],
            )

            texto = resposta.content[0].text
            categorias = _extrair_json_resposta(texto)

            # Valida e sanitiza as respostas
            categorias_validas = []
            for cat in categorias:
                dre_line = cat.get("dre_line", "outros")
                if dre_line not in LINHAS_DRE_VALIDAS:
                    dre_line = "outros"
                categorias_validas.append({
                    "id": cat.get("id"),
                    "category": cat.get("category", "Não categorizado"),
                    "subcategory": cat.get("subcategory"),
                    "dre_line": dre_line,
                    "confidence": min(1.0, max(0.0, float(cat.get("confidence", 0.5)))),
                })

            return categorias_validas

        except anthropic.APITimeoutError:
            logger.warning(f"Timeout na tentativa {tentativa}/{MAX_TENTATIVAS}")
        except anthropic.RateLimitError:
            logger.warning(f"Rate limit na tentativa {tentativa}/{MAX_TENTATIVAS}")
        except Exception as e:
            logger.warning(f"Erro na tentativa {tentativa}/{MAX_TENTATIVAS}: {e}")

        if tentativa < MAX_TENTATIVAS:
            espera = BACKOFF_BASE ** tentativa
            logger.info(f"Aguardando {espera}s antes de tentar novamente...")
            await asyncio.sleep(espera)

    # Se todas as tentativas falharam, retorna categorias neutras
    logger.error(f"Categorização falhou após {MAX_TENTATIVAS} tentativas. Usando 'outros'.")
    return [
        {
            "id": t.get("id") or f"t_{i}",
            "category": "Não categorizado",
            "subcategory": None,
            "dre_line": "outros",
            "confidence": 0.0,
        }
        for i, t in enumerate(lote)
    ]


async def categorizar_transacoes(
    transacoes: list[dict[str, Any]],
    tenant_id: str,
) -> list[dict[str, Any]]:
    """
    Categoriza lista de transações usando Claude API.
    Processa em lotes de até 50 transações.

    Retorna as transações originais enriquecidas com campos de categorização.
    """
    if not transacoes:
        return []

    # Busca contexto do tenant
    client_db = get_supabase_client()
    tenant_data = client_db.table("tenants").select("tax_regime").eq("id", tenant_id).single().execute()
    regime = tenant_data.data.get("tax_regime", "simples") if tenant_data.data else "simples"

    contas = get_chart_of_accounts(tenant_id)
    plano_contas = _formatar_plano_contas(contas)

    cliente_anthropic = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Cria mapa de índice por ID para mesclar resultados
    id_para_indice: dict[str, int] = {}
    for i, t in enumerate(transacoes):
        tid = t.get("id") or f"t_{i}"
        t["_idx_id"] = tid
        id_para_indice[tid] = i

    # Processa em lotes
    resultados_categorizados: list[dict | None] = [None] * len(transacoes)

    for inicio in range(0, len(transacoes), TAMANHO_LOTE):
        lote = transacoes[inicio : inicio + TAMANHO_LOTE]
        numero_lote = inicio // TAMANHO_LOTE + 1
        total_lotes = (len(transacoes) + TAMANHO_LOTE - 1) // TAMANHO_LOTE
        logger.info(f"Categorizando lote {numero_lote}/{total_lotes} ({len(lote)} transações)")

        categorias_lote = await _categorizar_lote(cliente_anthropic, lote, plano_contas, regime)

        # Mescla categorias de volta nas transações
        for i, cat in enumerate(categorias_lote):
            tid = cat.get("id") or lote[i].get("_idx_id")
            idx = id_para_indice.get(str(tid), inicio + i)
            if idx < len(transacoes):
                resultados_categorizados[idx] = cat

    # Constrói lista final mesclando transações originais com categorias
    transacoes_finais = []
    for i, transacao in enumerate(transacoes):
        cat = resultados_categorizados[i] or {}
        transacao_final = {**transacao}
        transacao_final.pop("_idx_id", None)
        transacao_final.update({
            "category": cat.get("category"),
            "subcategory": cat.get("subcategory"),
            "dre_line": cat.get("dre_line", "outros"),
            "confidence": cat.get("confidence", 0.0),
        })
        transacoes_finais.append(transacao_final)

    logger.info(f"Categorização concluída: {len(transacoes_finais)} transações processadas")
    return transacoes_finais
