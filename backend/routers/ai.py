"""
Router de inteligência artificial — Agente FinPME.
Implementa chat agêntico com Tool Use do Claude + streaming SSE.
"""

import asyncio
import json
import logging
import os
from datetime import date

import anthropic
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from db.supabase import get_tenant
from models.schemas import AgentChatRequest, ChatMessage, ChatResponse
from services.agent_tools import FERRAMENTAS, execute_tool

logger = logging.getLogger(__name__)
router = APIRouter()

MODELO_CLAUDE = "claude-sonnet-4-20250514"
MAX_ITERACOES = 5  # Evita loop infinito de tool use


def _sistema_prompt(tenant: dict | None) -> str:
    nome_empresa = tenant.get("name", "sua empresa") if tenant else "sua empresa"
    regime = tenant.get("tax_regime", "simples") if tenant else "simples"
    hoje = date.today().strftime("%d/%m/%Y")

    return f"""Você é o assistente financeiro inteligente da {nome_empresa}, uma PME brasileira.
Regime fiscal: {regime}. Data de hoje: {hoje}.

Você pode executar ações reais como gerar DRE, fluxo de caixa, buscar transações e criar resumos financeiros.
Quando o usuário pedir algo que exige dados, use as ferramentas disponíveis — não invente números.

Ao usar as ferramentas:
- Para períodos como "março" ou "mês passado", calcule as datas corretas com base na data de hoje
- Prefira respostas diretas e em português, com formatação clara usando markdown
- Apresente valores financeiros em reais (R$) com separador de milhar
- Seja objetivo e prático — o usuário é empreendedor, não contador

Após usar uma ferramenta, interprete os dados e responda de forma clara e útil."""


async def _stream_agente(tenant_id: str, tenant: dict | None, mensagens: list[dict]):
    """
    Generator assíncrono que implementa o agentic loop com streaming SSE.
    Itera até Claude não solicitar mais ferramentas ou atingir MAX_ITERACOES.
    """
    cliente = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    historico = list(mensagens)

    try:
        for _ in range(MAX_ITERACOES):
            async with cliente.messages.stream(
                model=MODELO_CLAUDE,
                max_tokens=2048,
                system=_sistema_prompt(tenant),
                tools=FERRAMENTAS,
                messages=historico,
            ) as stream:
                # Envia texto em tempo real conforme chega
                async for texto in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'content': texto})}\n\n"

                # Aguarda mensagem completa para processar tool_use
                mensagem_final = await stream.get_final_message()

            # Adiciona resposta do assistente ao histórico interno
            historico.append({
                "role": "assistant",
                "content": mensagem_final.content,
            })

            # Se não há chamada de ferramenta, encerra o loop
            if mensagem_final.stop_reason != "tool_use":
                break

            # Processa ferramentas solicitadas
            resultados_ferramentas = []
            for bloco in mensagem_final.content:
                if bloco.type == "tool_use":
                    nome = bloco.name
                    params = bloco.input

                    logger.info(f"Agente executando: {nome} | params={params} | tenant={tenant_id}")
                    yield f"data: {json.dumps({'type': 'tool_start', 'name': nome})}\n\n"

                    # Executa em thread pool para não bloquear o event loop
                    resultado = await asyncio.to_thread(execute_tool, nome, params, tenant_id)

                    yield f"data: {json.dumps({'type': 'tool_result', 'name': nome, 'result': resultado})}\n\n"

                    resultados_ferramentas.append({
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": json.dumps(resultado, ensure_ascii=False, default=str),
                    })

            if resultados_ferramentas:
                historico.append({"role": "user", "content": resultados_ferramentas})

    except anthropic.APITimeoutError:
        yield f"data: {json.dumps({'type': 'error', 'message': 'O assistente demorou muito. Tente novamente.'})}\n\n"
    except anthropic.APIError as e:
        logger.error(f"Erro na API Anthropic: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'Erro ao consultar o assistente.'})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/agent")
async def agente_financeiro(req: AgentChatRequest, request: Request):
    """
    Agente financeiro com Tool Use e streaming SSE.
    Recebe histórico de mensagens e retorna stream de eventos SSE.
    """
    tenant_id: str = request.state.tenant_id
    tenant = get_tenant(tenant_id)

    # Converte para dicts e limita às últimas 20 mensagens (10 trocas)
    mensagens = [
        {"role": m.role, "content": m.content}
        for m in req.messages[-20:]
    ]

    return StreamingResponse(
        _stream_agente(tenant_id, tenant, mensagens),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat")
async def chat_financeiro(mensagem: ChatMessage, request: Request):
    """Chat simples sem streaming (mantido para compatibilidade)."""
    tenant_id: str = request.state.tenant_id
    tenant = get_tenant(tenant_id)

    try:
        cliente = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resposta = cliente.messages.create(
            model=MODELO_CLAUDE,
            max_tokens=1024,
            system=_sistema_prompt(tenant),
            messages=[{"role": "user", "content": mensagem.message}],
        )
        return ChatResponse(reply=resposta.content[0].text)
    except anthropic.APITimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="O assistente demorou muito para responder.",
        )
    except anthropic.APIError as e:
        logger.error(f"Erro na API Anthropic: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao consultar assistente de IA",
        )
