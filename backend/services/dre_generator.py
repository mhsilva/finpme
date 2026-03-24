"""
Gerador de DRE (Demonstração de Resultado do Exercício).
Agrupa transações por linha do DRE e calcula indicadores financeiros.
"""

import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from db.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# Arredondamento padrão para valores monetários
CENTS = Decimal("0.01")


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTS, rounding=ROUND_HALF_UP)


def _percentual(valor: Decimal, base: Decimal) -> Decimal:
    """Calcula percentual de valor sobre base. Retorna 0 se base for zero."""
    if base == Decimal("0"):
        return Decimal("0")
    return _arredondar((valor / base) * 100)


def generate_dre(tenant_id: str, start: date, end: date) -> dict:
    """
    Gera o DRE para o tenant no período especificado.

    Considera transações:
    - Confirmadas manualmente pelo usuário (confirmed = TRUE), OU
    - Categorizadas pela IA com confiança > 0.85

    Retorna estrutura completa com valores e percentuais sobre receita líquida.
    """
    client = get_supabase_client()

    resultado = (
        client.table("transactions")
        .select("dre_line, amount, confirmed, ai_confidence")
        .eq("tenant_id", tenant_id)
        .gte("date", start.isoformat())
        .lte("date", end.isoformat())
        .not_.is_("dre_line", "null")
        .execute()
    )

    transacoes = resultado.data or []
    logger.info(f"DRE: {len(transacoes)} transações encontradas para tenant {tenant_id}")

    # Agrupa por linha do DRE (apenas transações confiáveis)
    totais: dict[str, Decimal] = {
        "receita_bruta": Decimal("0"),
        "deducoes": Decimal("0"),
        "cmv": Decimal("0"),
        "despesa_vendas": Decimal("0"),
        "despesa_admin": Decimal("0"),
        "despesa_financeira": Decimal("0"),
        "outros": Decimal("0"),
    }

    for t in transacoes:
        confirmado = t.get("confirmed", False)
        confianca = float(t.get("ai_confidence") or 0)
        linha = t.get("dre_line", "outros")

        if not (confirmado or confianca > 0.85):
            continue

        if linha not in totais:
            linha = "outros"

        totais[linha] += Decimal(str(t["amount"]))

    # Cálculos do DRE
    receita_bruta = _arredondar(totais["receita_bruta"])
    deducoes = _arredondar(abs(totais["deducoes"]))  # Deduções são sempre positivas no relatório
    receita_liquida = _arredondar(receita_bruta - deducoes)

    cmv = _arredondar(abs(totais["cmv"]))
    lucro_bruto = _arredondar(receita_liquida - cmv)

    despesa_vendas = _arredondar(abs(totais["despesa_vendas"]))
    despesa_admin = _arredondar(abs(totais["despesa_admin"]))
    despesa_financeira = _arredondar(abs(totais["despesa_financeira"]))
    total_despesas_op = _arredondar(despesa_vendas + despesa_admin + despesa_financeira)

    ebitda = _arredondar(lucro_bruto - despesa_vendas - despesa_admin)
    outros = _arredondar(totais["outros"])
    lucro_liquido = _arredondar(ebitda - despesa_financeira + outros)

    dre = {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        # Receitas
        "receita_bruta": float(receita_bruta),
        "deducoes": float(deducoes),
        "receita_liquida": float(receita_liquida),
        # CMV
        "cmv": float(cmv),
        "lucro_bruto": float(lucro_bruto),
        # Despesas operacionais
        "despesa_vendas": float(despesa_vendas),
        "despesa_admin": float(despesa_admin),
        "despesa_financeira": float(despesa_financeira),
        "total_despesas_operacionais": float(total_despesas_op),
        # Resultado
        "ebitda": float(ebitda),
        "outros": float(outros),
        "lucro_liquido": float(lucro_liquido),
        # Percentuais sobre receita líquida
        "margem_bruta": float(_percentual(lucro_bruto, receita_liquida)),
        "margem_ebitda": float(_percentual(ebitda, receita_liquida)),
        "margem_liquida": float(_percentual(lucro_liquido, receita_liquida)),
    }

    logger.info(
        f"DRE gerado: receita={receita_bruta}, lucro_liquido={lucro_liquido}, "
        f"margem={_percentual(lucro_liquido, receita_liquida)}%"
    )
    return dre
