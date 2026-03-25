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
        "name": "listar_pendentes",
        "description": (
            "Lista transações ainda não confirmadas pelo usuário (confirmed = false). "
            "Use quando o usuário perguntar quais pagamentos estão pendentes ou precisam de confirmação. "
            "Retorna os IDs necessários para confirmar via confirmar_transacao."
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
            },
            "required": [],
        },
    },
    {
        "name": "confirmar_transacao",
        "description": (
            "Confirma uma ou mais transações pelo ID, marcando-as como verificadas pelo usuário. "
            "Use após listar_pendentes quando o usuário pedir para confirmar pagamentos específicos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transaction_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de IDs das transações a confirmar",
                },
            },
            "required": ["transaction_ids"],
        },
    },
    {
        "name": "resumo_centro_custo",
        "description": (
            "Retorna o relatório de gastos de um centro de custo: total realizado, orçamento e "
            "utilização percentual no período. Use quando o usuário perguntar sobre gastos por "
            "departamento, projeto ou centro de custo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "centro_custo_id": {
                    "type": "string",
                    "description": "ID do centro de custo (UUID)",
                },
                "inicio": {
                    "type": "string",
                    "description": "Data de início no formato YYYY-MM-DD",
                },
                "fim": {
                    "type": "string",
                    "description": "Data de fim no formato YYYY-MM-DD",
                },
            },
            "required": ["centro_custo_id", "inicio", "fim"],
        },
    },
    {
        "name": "resumo_conciliacao",
        "description": (
            "Retorna o status da conciliação bancária: quantas transações estão conciliadas, "
            "pendentes e o percentual de cobertura. "
            "Use quando o usuário perguntar sobre a saúde da conciliação ou lançamentos não conciliados."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "listar_contas_pagar",
        "description": (
            "Lista contas a pagar com filtros por status e período de vencimento. "
            "Use quando o usuário perguntar sobre pagamentos futuros, obrigações, boletos ou fornecedores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string", "description": "Data de início (YYYY-MM-DD)"},
                "fim":    {"type": "string", "description": "Data de fim (YYYY-MM-DD)"},
                "status": {"type": "string", "enum": ["pending", "overdue", "paid", "partial"], "description": "Filtro de status (opcional)"},
            },
            "required": [],
        },
    },
    {
        "name": "listar_contas_receber",
        "description": (
            "Lista contas a receber com filtros por status e período de vencimento. "
            "Use quando o usuário perguntar sobre recebíveis, clientes, entradas previstas ou inadimplência."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "inicio": {"type": "string", "description": "Data de início (YYYY-MM-DD)"},
                "fim":    {"type": "string", "description": "Data de fim (YYYY-MM-DD)"},
                "status": {"type": "string", "enum": ["pending", "overdue", "paid", "partial"], "description": "Filtro de status (opcional)"},
            },
            "required": [],
        },
    },
    {
        "name": "alertas_vencimento",
        "description": (
            "Retorna contas vencidas e contas que vencem nos próximos 7 dias (a pagar e a receber). "
            "Use quando o usuário perguntar sobre urgências, o que precisa pagar esta semana ou alertas financeiros."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "listar_centros_custo",
        "description": (
            "Lista todos os centros de custo ativos da empresa. "
            "Use quando o usuário perguntar quais departamentos ou projetos existem."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "lancar_transacao",
        "description": (
            "Cria um lançamento financeiro manual (entrada ou saída de caixa). "
            "Use quando o usuário quiser registrar um pagamento, recebimento ou qualquer movimentação "
            "que não veio de extrato importado. Exemplos: 'lança uma saída de 500 reais de aluguel', "
            "'registra entrada de 3000 de venda'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Data da transação no formato YYYY-MM-DD",
                },
                "description": {
                    "type": "string",
                    "description": "Descrição do lançamento",
                },
                "amount": {
                    "type": "number",
                    "description": "Valor: positivo = entrada/crédito, negativo = saída/débito",
                },
                "category": {
                    "type": "string",
                    "description": "Categoria do lançamento (opcional, ex: Aluguel, Vendas, Salários)",
                },
            },
            "required": ["date", "description", "amount"],
        },
    },
    {
        "name": "criar_conta_pagar",
        "description": (
            "Registra uma nova conta a pagar (obrigação futura). "
            "Use quando o usuário mencionar uma fatura, boleto, fornecedor ou qualquer pagamento "
            "que ainda vai acontecer. Exemplos: 'cria conta pra pagar fornecedor X 1500 reais', "
            "'registra boleto de energia 280 reais vence dia 10'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Descrição da conta",
                },
                "amount": {
                    "type": "number",
                    "description": "Valor positivo a pagar",
                },
                "due_date": {
                    "type": "string",
                    "description": "Data de vencimento no formato YYYY-MM-DD",
                },
                "contact_name": {
                    "type": "string",
                    "description": "Nome do fornecedor ou credor (opcional)",
                },
                "notes": {
                    "type": "string",
                    "description": "Observações adicionais (opcional)",
                },
            },
            "required": ["description", "amount", "due_date"],
        },
    },
    {
        "name": "criar_conta_receber",
        "description": (
            "Registra uma nova conta a receber (recebimento futuro). "
            "Use quando o usuário mencionar uma venda a prazo, cobrança ou qualquer recebimento "
            "que ainda vai acontecer. Exemplos: 'cria conta a receber do cliente Y 2000 reais', "
            "'registra NF de venda 5000 reais vence semana que vem'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Descrição da conta",
                },
                "amount": {
                    "type": "number",
                    "description": "Valor positivo a receber",
                },
                "due_date": {
                    "type": "string",
                    "description": "Data de vencimento/previsão no formato YYYY-MM-DD",
                },
                "contact_name": {
                    "type": "string",
                    "description": "Nome do cliente ou devedor (opcional)",
                },
                "notes": {
                    "type": "string",
                    "description": "Observações adicionais (opcional)",
                },
            },
            "required": ["description", "amount", "due_date"],
        },
    },
    {
        "name": "registrar_pagamento",
        "description": (
            "Marca uma conta a pagar ou receber como paga/recebida. "
            "Use quando o usuário disser que pagou uma conta ou recebeu um valor. "
            "Precisa do ID da conta — use listar_contas_pagar ou listar_contas_receber primeiro "
            "para obter o ID se necessário."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conta_id": {
                    "type": "string",
                    "description": "ID (UUID) da conta a pagar ou receber",
                },
                "paid_date": {
                    "type": "string",
                    "description": "Data do pagamento no formato YYYY-MM-DD (padrão: hoje)",
                },
            },
            "required": ["conta_id"],
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
        elif nome == "listar_pendentes":
            return _tool_listar_pendentes(parametros, tenant_id)
        elif nome == "confirmar_transacao":
            return _tool_confirmar_transacao(parametros, tenant_id)
        elif nome == "resumo_periodo":
            return _tool_resumo_periodo(parametros, tenant_id)
        elif nome == "resumo_centro_custo":
            return _tool_resumo_centro_custo(parametros, tenant_id)
        elif nome == "listar_centros_custo":
            return _tool_listar_centros_custo(parametros, tenant_id)
        elif nome == "resumo_conciliacao":
            return _tool_resumo_conciliacao(parametros, tenant_id)
        elif nome == "listar_contas_pagar":
            return _tool_listar_contas(parametros, tenant_id, tipo="payable")
        elif nome == "listar_contas_receber":
            return _tool_listar_contas(parametros, tenant_id, tipo="receivable")
        elif nome == "alertas_vencimento":
            return _tool_alertas_vencimento(parametros, tenant_id)
        elif nome == "lancar_transacao":
            return _tool_lancar_transacao(parametros, tenant_id)
        elif nome == "criar_conta_pagar":
            return _tool_criar_conta_pr(parametros, tenant_id, tipo="payable")
        elif nome == "criar_conta_receber":
            return _tool_criar_conta_pr(parametros, tenant_id, tipo="receivable")
        elif nome == "registrar_pagamento":
            return _tool_registrar_pagamento(parametros, tenant_id)
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


def _tool_listar_pendentes(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()

    query = (
        client.table("transactions")
        .select("id, date, description, amount, category")
        .eq("tenant_id", tenant_id)
        .eq("confirmed", False)
        .order("date", desc=True)
        .limit(50)
    )

    if parametros.get("inicio"):
        query = query.gte("date", parametros["inicio"])
    if parametros.get("fim"):
        query = query.lte("date", parametros["fim"])

    resultado = query.execute()
    transacoes = resultado.data or []

    return {
        "total": len(transacoes),
        "pendentes": [
            {
                "id": t["id"],
                "data": t["date"],
                "descricao": t["description"],
                "valor": float(t["amount"]),
                "categoria": t.get("category") or "Não categorizado",
            }
            for t in transacoes
        ],
    }


def _tool_confirmar_transacao(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    ids = parametros.get("transaction_ids", [])
    confirmados = []
    nao_encontrados = []

    for tid in ids:
        try:
            resultado = (
                client.table("transactions")
                .update({"confirmed": True})
                .eq("id", tid)
                .eq("tenant_id", tenant_id)  # garante isolamento por tenant
                .execute()
            )
            if resultado.data:
                confirmados.append(tid)
            else:
                nao_encontrados.append(tid)
        except Exception as e:
            logger.error(f"Erro ao confirmar transação {tid}: {e}")
            nao_encontrados.append(tid)

    return {
        "confirmados": len(confirmados),
        "nao_encontrados": len(nao_encontrados),
        "mensagem": f"{len(confirmados)} transação(ões) confirmada(s) com sucesso.",
    }


def _tool_resumo_conciliacao(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()

    total_res = (
        client.table("transactions")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    conc_res = (
        client.table("reconciliation_matches")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    total       = total_res.count or 0
    conciliadas = conc_res.count or 0
    pendentes   = total - conciliadas

    return {
        "total_transacoes":  total,
        "conciliadas":       conciliadas,
        "nao_conciliadas":   pendentes,
        "pct_conciliado":    round((conciliadas / total * 100) if total > 0 else 0, 1),
        "status": "ok" if pendentes == 0 else ("atencao" if pendentes <= 10 else "critico"),
    }


def _tool_listar_contas(parametros: dict, tenant_id: str, tipo: str) -> dict:
    from datetime import date as _date
    client = get_supabase_client()

    # Auto-atualiza vencidas
    hoje = _date.today().isoformat()
    client.table("payables_receivables").update({"status": "overdue"}).eq(
        "tenant_id", tenant_id
    ).eq("status", "pending").lt("due_date", hoje).execute()

    query = (
        client.table("payables_receivables")
        .select("id, description, amount, due_date, paid_date, status, contact_name, installments_total, installments_num")
        .eq("tenant_id", tenant_id)
        .eq("type", tipo)
        .neq("status", "cancelled")
        .order("due_date")
        .limit(50)
    )
    if parametros.get("inicio"):
        query = query.gte("due_date", parametros["inicio"])
    if parametros.get("fim"):
        query = query.lte("due_date", parametros["fim"])
    if parametros.get("status"):
        query = query.eq("status", parametros["status"])

    res = query.execute()
    contas = res.data or []

    total = sum(float(c["amount"]) for c in contas if c["status"] != "paid")
    label = "pagar" if tipo == "payable" else "receber"

    return {
        "total_contas": len(contas),
        f"total_a_{label}": round(total, 2),
        "contas": [
            {
                "id": c["id"],
                "descricao": c["description"],
                "valor": float(c["amount"]),
                "vencimento": c["due_date"],
                "status": c["status"],
                "contato": c.get("contact_name"),
                "parcela": f"{c['installments_num']}/{c['installments_total']}" if c["installments_total"] > 1 else None,
            }
            for c in contas
        ],
    }


def _tool_alertas_vencimento(parametros: dict, tenant_id: str) -> dict:
    from datetime import date as _date, timedelta
    client = get_supabase_client()

    hoje = _date.today()
    em7dias = (hoje + timedelta(days=7)).isoformat()
    hoje_str = hoje.isoformat()

    # Auto-atualiza vencidas
    client.table("payables_receivables").update({"status": "overdue"}).eq(
        "tenant_id", tenant_id
    ).eq("status", "pending").lt("due_date", hoje_str).execute()

    # Vencidas (overdue)
    vencidas_res = (
        client.table("payables_receivables")
        .select("type, description, amount, due_date, contact_name")
        .eq("tenant_id", tenant_id)
        .eq("status", "overdue")
        .order("due_date")
        .limit(20)
        .execute()
    )

    # Próximos 7 dias
    proximas_res = (
        client.table("payables_receivables")
        .select("type, description, amount, due_date, contact_name")
        .eq("tenant_id", tenant_id)
        .eq("status", "pending")
        .gte("due_date", hoje_str)
        .lte("due_date", em7dias)
        .order("due_date")
        .limit(20)
        .execute()
    )

    vencidas = vencidas_res.data or []
    proximas = proximas_res.data or []

    total_vencido   = sum(float(c["amount"]) for c in vencidas)
    total_proximos  = sum(float(c["amount"]) for c in proximas)

    def fmt(c):
        return {
            "tipo": "pagar" if c["type"] == "payable" else "receber",
            "descricao": c["description"],
            "valor": float(c["amount"]),
            "vencimento": c["due_date"],
            "contato": c.get("contact_name"),
        }

    return {
        "vencidas": {
            "total_registros": len(vencidas),
            "total_valor": round(total_vencido, 2),
            "contas": [fmt(c) for c in vencidas],
        },
        "proximas_7_dias": {
            "total_registros": len(proximas),
            "total_valor": round(total_proximos, 2),
            "contas": [fmt(c) for c in proximas],
        },
    }


def _tool_listar_centros_custo(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    res = (
        client.table("cost_centers")
        .select("id, name, code, type, budget")
        .eq("tenant_id", tenant_id)
        .eq("active", True)
        .order("name")
        .execute()
    )
    centros = res.data or []
    return {
        "total": len(centros),
        "centros": [
            {
                "id": c["id"],
                "nome": c["name"],
                "codigo": c["code"],
                "tipo": c["type"],
                "orcamento_mensal": float(c["budget"]) if c.get("budget") else None,
            }
            for c in centros
        ],
    }


def _tool_resumo_centro_custo(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    centro_id = parametros["centro_custo_id"]
    inicio = parametros["inicio"]
    fim = parametros["fim"]

    cc_res = (
        client.table("cost_centers")
        .select("name, code, budget")
        .eq("id", centro_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not cc_res.data:
        return {"erro": f"Centro de custo {centro_id} não encontrado"}
    cc = cc_res.data

    aloc_res = (
        client.table("transaction_cost_centers")
        .select("amount, transactions(date, category)")
        .eq("tenant_id", tenant_id)
        .eq("cost_center_id", centro_id)
        .execute()
    )
    alocacoes = [
        a for a in (aloc_res.data or [])
        if a.get("transactions") and inicio <= a["transactions"]["date"] <= fim
    ]

    total_gasto = sum(abs(float(a["amount"])) for a in alocacoes)
    orcamento = float(cc.get("budget") or 0)

    gastos_cat: dict[str, float] = {}
    for a in alocacoes:
        cat = a["transactions"].get("category") or "Não categorizado"
        gastos_cat[cat] = gastos_cat.get(cat, 0) + abs(float(a["amount"]))

    return {
        "centro": cc["name"],
        "codigo": cc["code"],
        "periodo": {"inicio": inicio, "fim": fim},
        "total_gasto": round(total_gasto, 2),
        "orcamento_mensal": orcamento,
        "utilizacao_pct": round((total_gasto / orcamento * 100) if orcamento > 0 else 0, 1),
        "gastos_por_categoria": sorted(
            [{"categoria": k, "total": round(v, 2)} for k, v in gastos_cat.items()],
            key=lambda x: x["total"],
            reverse=True,
        )[:5],
    }


def _tool_lancar_transacao(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    registro = {
        "tenant_id":      tenant_id,
        "date":           parametros["date"],
        "description":    parametros["description"],
        "amount":         float(parametros["amount"]),
        "category":       parametros.get("category"),
        "source":         "manual_agent",
        "ai_categorized": False,
        "confirmed":      True,
    }
    res = client.table("transactions").insert(registro).execute()
    if not res.data:
        return {"erro": "Falha ao criar lançamento"}
    criado = res.data[0]
    tipo = "entrada" if float(parametros["amount"]) > 0 else "saída"
    return {
        "id": criado["id"],
        "mensagem": f"Lançamento de {tipo} criado com sucesso.",
        "descricao": criado["description"],
        "valor": float(criado["amount"]),
        "data": criado["date"],
    }


def _tool_criar_conta_pr(parametros: dict, tenant_id: str, tipo: str) -> dict:
    client = get_supabase_client()
    registro = {
        "tenant_id":    tenant_id,
        "type":         tipo,
        "description":  parametros["description"],
        "amount":       float(parametros["amount"]),
        "due_date":     parametros["due_date"],
        "contact_name": parametros.get("contact_name"),
        "notes":        parametros.get("notes"),
        "status":       "pending",
    }
    res = client.table("payables_receivables").insert(registro).execute()
    if not res.data:
        return {"erro": "Falha ao criar conta"}
    criado = res.data[0]
    label = "pagar" if tipo == "payable" else "receber"
    return {
        "id": criado["id"],
        "mensagem": f"Conta a {label} criada com sucesso.",
        "descricao": criado["description"],
        "valor": float(criado["amount"]),
        "vencimento": criado["due_date"],
    }


def _tool_registrar_pagamento(parametros: dict, tenant_id: str) -> dict:
    from datetime import date as _date
    client = get_supabase_client()
    conta_id = parametros["conta_id"]
    paid_date = parametros.get("paid_date") or _date.today().isoformat()

    res = (
        client.table("payables_receivables")
        .update({"status": "paid", "paid_date": paid_date})
        .eq("id", conta_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not res.data:
        return {"erro": f"Conta {conta_id} não encontrada ou sem permissão"}
    conta = res.data[0]
    label = "pagar" if conta["type"] == "payable" else "receber"
    return {
        "mensagem": f"Conta a {label} '{conta['description']}' marcada como paga.",
        "valor": float(conta["amount"]),
        "data_pagamento": paid_date,
    }


def _tool_resumo_periodo(parametros: dict, tenant_id: str) -> dict:
    client = get_supabase_client()
    inicio = parametros["inicio"]
    fim = parametros["fim"]

    resultado = (
        client.table("transactions")
        .select("amount, category")
        .eq("tenant_id", tenant_id)
        .eq("confirmed", True)
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
