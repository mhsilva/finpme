"""
Router de inteligência artificial.
Chat financeiro livre usando Claude com contexto do tenant.
"""

import logging
import os
from decimal import Decimal

import anthropic
from fastapi import APIRouter, HTTPException, Request, status

from db.supabase import get_supabase_client, get_tenant
from models.schemas import ChatMessage, ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()

MODELO_CLAUDE = "claude-sonnet-4-20250514"
TIMEOUT_ANTHROPIC = 30


def _buscar_contexto_financeiro(tenant_id: str) -> dict:
    """
    Busca contexto financeiro resumido do tenant para incluir no prompt:
    - Saldo atual (últimos 30 dias)
    - 5 maiores despesas do mês
    - Receita do mês
    """
    client = get_supabase_client()
    from datetime import date, timedelta

    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    try:
        resultado = (
            client.table("transactions")
            .select("amount, category, description, date")
            .eq("tenant_id", tenant_id)
            .gte("date", inicio_mes.isoformat())
            .lte("date", hoje.isoformat())
            .execute()
        )
        transacoes = resultado.data or []
    except Exception:
        transacoes = []

    receita = sum(float(t["amount"]) for t in transacoes if float(t["amount"]) > 0)
    despesas = sum(float(t["amount"]) for t in transacoes if float(t["amount"]) < 0)
    saldo = receita + despesas  # despesas já são negativas

    # Top 5 maiores despesas
    maiores_despesas = sorted(
        [t for t in transacoes if float(t["amount"]) < 0],
        key=lambda x: float(x["amount"]),
    )[:5]

    return {
        "mes_referencia": inicio_mes.strftime("%B/%Y"),
        "receita_mes": receita,
        "despesas_mes": abs(despesas),
        "saldo_mes": saldo,
        "maiores_despesas": [
            {
                "descricao": t["description"],
                "categoria": t.get("category", "Não categorizado"),
                "valor": abs(float(t["amount"])),
            }
            for t in maiores_despesas
        ],
    }


@router.post("/chat")
async def chat_financeiro(mensagem: ChatMessage, request: Request):
    """
    Chat financeiro livre.
    Claude responde como assistente financeiro especializado em PMEs,
    com contexto dos dados do tenant.
    """
    tenant_id: str = request.state.tenant_id
    tenant = get_tenant(tenant_id)
    contexto_financeiro = _buscar_contexto_financeiro(tenant_id)

    nome_empresa = tenant.get("name", "sua empresa") if tenant else "sua empresa"
    regime = tenant.get("tax_regime", "simples") if tenant else "simples"

    sistema_prompt = f"""Você é o assistente financeiro da {nome_empresa}, uma PME brasileira.
Seu papel é ajudar o empresário a entender a saúde financeira do negócio, interpretar relatórios,
identificar oportunidades de economia e responder perguntas sobre o DRE e fluxo de caixa.

Informações da empresa:
- Regime fiscal: {regime}
- Mês de referência: {contexto_financeiro['mes_referencia']}
- Receita do mês: R$ {contexto_financeiro['receita_mes']:,.2f}
- Despesas do mês: R$ {contexto_financeiro['despesas_mes']:,.2f}
- Saldo do mês: R$ {contexto_financeiro['saldo_mes']:,.2f}

Maiores despesas do mês:
{chr(10).join(f"- {d['descricao']} ({d['categoria']}): R$ {d['valor']:,.2f}" for d in contexto_financeiro['maiores_despesas'])}

Responda sempre em português, de forma clara e objetiva. Use linguagem acessível para
empreendedores que não são contadores. Quando relevante, sugira ações práticas."""

    try:
        cliente_anthropic = anthropic.Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
        )

        resposta = cliente_anthropic.messages.create(
            model=MODELO_CLAUDE,
            max_tokens=1024,
            timeout=TIMEOUT_ANTHROPIC,
            system=sistema_prompt,
            messages=[
                {"role": "user", "content": mensagem.message}
            ],
        )

        texto_resposta = resposta.content[0].text
        logger.info(f"Chat respondido para tenant {tenant_id}")
        return ChatResponse(reply=texto_resposta)

    except anthropic.APITimeoutError:
        logger.error(f"Timeout na API Anthropic para tenant {tenant_id}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="O assistente demorou muito para responder. Tente novamente.",
        )
    except anthropic.APIError as e:
        logger.error(f"Erro na API Anthropic: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao consultar assistente de IA",
        )
