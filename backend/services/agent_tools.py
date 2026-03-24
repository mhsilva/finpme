"""
Definições de ferramentas (tools) para o agente FinPME.
Implementa o pattern Tool Use do Claude com agentic loop.
"""

import json
import logging
from datetime import date
from typing import Any

from db.supabase import get_supabase_client
from services.cashflow_generator import generate_cashflow
from services.dre_generator import generate_dre

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Definições das ferramentas (formato Anthropic Tool Use)
# ---------------------------------------------------------------------------

FERRAMENTAS = [
    {
        "name": "gerar_dre",
        "description": (
            "Gera o DRE (Demonstração de Resultado do Exercício) para um período. "
            "Use quando o usuário pedir DRE, resultado, lucro, receita, despesas do período."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {
                    "type": "string",
                    "description": "Data de início no formato YYYY-MM-DD (ex: 2025-03-01)",
                },
                "fim": {
                    "type": "string",
                    "description": "Data de fim no formato YYYY-MM-DD (ex: 2025-03-31)",
                },
            },
            "required": ["inicio", "fim"],
        },
    },
    {
        "name": "gerar_fluxo_caixa",
        "description": (
            "Gera o fluxo de caixa semanal para um período. "
            "Use quando o usuário pedir fluxo de caixa, entradas e saídas, saldo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {
                    "type": "string",
                    "description": "Data de início no formato YYYY-MM-DD",
                },
                "fim": {
                    "type": "string",
                    "description": "Data de fim no formato YYYY-MM-DD",
                },
            },
            "required": ["inicio", "fim"],
        },
    },
    {
        "name": "buscar_transacoes",
        "description": (
            "Busca transações financeiras com filtros opcionais. "
            "Use quando o usuário perguntar sobre lançamentos específicos, categorias ou transações."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {
                    "type": "string",
                    "description": "Data de início no formato YYYY-MM-DD (opcional)",
                },
                "fim": {
                    "type": "string",
                    "description": "Data de fim no formato YYYY-MM-DD (opcional)",
                },
                "categoria": {
                    "type": "string",
                    "description": "Filtrar por categoria (opcional)",
                },
                "tipo": {
                    "type": "string",
                    "enum": ["entrada", "saida"],
                    "description": "Tipo: 'entrada' (positivo) ou 'saida' (negativo) (opcional)",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de transações a retornar (padrão: 20)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "resumo_periodo",
        "description": (
            "Retorna um resumo financeiro rápido de um período: receita total, despesas totais, "
            "saldo e as principais categorias de gastos. "
            "Use quando o usuário quiser um overview, resumo ou diagnóstico rápido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {
                    "type": "string",
                    "description": "Data de início no formato YYYY-MM-DD",
                },
                "fim": {
                    "type": "string",
                    "description": "Data de fim no formato YYYY-MM-DD",
                },
            },
            "required": ["inicio", "fim"],
        },
    },
]


# ---------------------------------------------------------------------------
# Execução das ferramentas
# ---------------------------------------------------------------------------


def execute_tool(nome: str, parametros: dict, tenant_id: str) -> Any:
    """
    Executa uma ferramenta e retorna o resultado como dict serializável.
    """
    try:
        if nome == "gerar_dre":
            return _tool_gerar_dre(parametros, tenant_id)
        elif nome == "gerar_fluxo_caixa":
            return _tool_gerar_fluxo_caixa(parametros, tenant_id)
        elif nome == "buscar_transacoes":
            return _tool_buscar_transacoes(parametros, tenant_id)
        elif nome == "resumo_periodo":
            return _tool_resumo_periodo(parametros, tenant_id)
        else:
            return {"erro": f"Ferramenta desconhecida: {nome}"}
    except Exception as e:
        logger.error(f"Erro ao executar ferramenta {nome}: {e}")
        return {"erro": str(e)}


def _tool_gerar_dre(parametros: dict, tenant_id: str) -> dict:
    inicio = date.fromisoformat(parametros["inicio"])
    fim = date.fromisoformat(parametros["fim"])
    return generate_dre(tenant_id, inicio, fim)


def _tool_gerar_fluxo_caixa(parametros: dict, tenant_id: str) -> dict:
    inicio = date.fromisoformat(parametros["inicio"])
    fim = date.fromisoformat(parametros["fim"])
    return generate_cashflow(tenant_id, inicio, fim)


def _tool_buscar_transacoes(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    limite = int(parametros.get("limite") or 20)

    query = (
        client.table("transactions")
        .select("id, date, description, amount, category, dre_line, confirmed, ai_confidence")
        .eq("tenant_id", tenant_id)
        .order("date", desc=True)
        .limit(limite)
    )

    if parametros.get("inicio"):
        query = query.gte("date", parametros["inicio"])
    if parametros.get("fim"):
        query = query.lte("date", parametros["fim"])
    if parametros.get("categoria"):
        query = query.ilike("category", f"%{parametros['categoria']}%")
    if parametros.get("tipo") == "entrada":
        query = query.gt("amount", 0)
    elif parametros.get("tipo") == "saida":
        query = query.lt("amount", 0)

    resultado = query.execute()
    transacoes = resultado.data or []

    return {
        "total": len(transacoes),
        "transacoes": [
            {
                "data": t["date"],
                "descricao": t["description"],
                "valor": float(t["amount"]),
                "categoria": t.get("category") or "Não categorizado",
                "confirmada": t.get("confirmed", False),
            }
            for t in transacoes
        ],
    }


def _tool_resumo_periodo(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    inicio = parametros["inicio"]
    fim = parametros["fim"]

    resultado = (
        client.table("transactions")
        .select("amount, category")
        .eq("tenant_id", tenant_id)
        .gte("date", inicio)
        .lte("date", fim)
        .execute()
    )

    transacoes = resultado.data or []

    receita = sum(float(t["amount"]) for t in transacoes if float(t["amount"]) > 0)
    despesas = sum(abs(float(t["amount"])) for t in transacoes if float(t["amount"]) < 0)

    gastos_por_categoria: dict[str, float] = {}
    for t in transacoes:
        if float(t["amount"]) < 0:
            cat = t.get("category") or "Não categorizado"
            gastos_por_categoria[cat] = gastos_por_categoria.get(cat, 0) + abs(float(t["amount"]))

    top_categorias = sorted(gastos_por_categoria.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "periodo": {"inicio": inicio, "fim": fim},
        "total_transacoes": len(transacoes),
        "receita_total": round(receita, 2),
        "despesas_total": round(despesas, 2),
        "saldo": round(receita - despesas, 2),
        "top_categorias_gasto": [
            {"categoria": cat, "total": round(valor, 2)}
            for cat, valor in top_categorias
        ],
    }
