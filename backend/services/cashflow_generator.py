"""
Gerador de Fluxo de Caixa.
Agrupa transações por semana e calcula saldo acumulado.
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from db.supabase import get_supabase_client

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")


def _inicio_semana(d: date) -> date:
    """Retorna a segunda-feira da semana de uma data."""
    return d - timedelta(days=d.weekday())


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(CENTS, rounding=ROUND_HALF_UP)


def generate_cashflow(tenant_id: str, start: date, end: date) -> dict:
    """
    Gera o fluxo de caixa agrupado por semana para o período especificado.

    Retorna:
    - Série temporal de entradas, saídas e saldo por semana
    - Totais do período
    - Saldo acumulado semana a semana
    """
    client = get_supabase_client()

    resultado = (
        client.table("transactions")
        .select("date, amount")
        .eq("tenant_id", tenant_id)
        .gte("date", start.isoformat())
        .lte("date", end.isoformat())
        .order("date")
        .execute()
    )

    transacoes = resultado.data or []
    logger.info(f"Fluxo de caixa: {len(transacoes)} transações para tenant {tenant_id}")

    # Agrupa por semana
    entradas_por_semana: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    saidas_por_semana: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for t in transacoes:
        data = date.fromisoformat(t["date"])
        semana = _inicio_semana(data)
        chave = semana.strftime("%Y-%m-%d")  # ISO da segunda-feira
        valor = Decimal(str(t["amount"]))

        if valor > 0:
            entradas_por_semana[chave] += valor
        else:
            saidas_por_semana[chave] += abs(valor)

    # Gera todas as semanas do período (mesmo sem movimentação)
    semanas_do_periodo: list[str] = []
    semana_atual = _inicio_semana(start)
    while semana_atual <= end:
        semanas_do_periodo.append(semana_atual.strftime("%Y-%m-%d"))
        semana_atual += timedelta(weeks=1)

    # Monta série temporal com saldo acumulado
    saldo_acumulado = Decimal("0")
    entradas: list[dict] = []

    for semana in semanas_do_periodo:
        entrada = _arredondar(entradas_por_semana.get(semana, Decimal("0")))
        saida = _arredondar(saidas_por_semana.get(semana, Decimal("0")))
        saldo_periodo = _arredondar(entrada - saida)
        saldo_acumulado = _arredondar(saldo_acumulado + saldo_periodo)

        entradas.append({
            "period": semana,
            "entradas": float(entrada),
            "saidas": float(saida),
            "saldo_periodo": float(saldo_periodo),
            "saldo_acumulado": float(saldo_acumulado),
        })

    total_entradas = _arredondar(sum(entradas_por_semana.values(), Decimal("0")))
    total_saidas = _arredondar(sum(saidas_por_semana.values(), Decimal("0")))
    saldo_final = _arredondar(total_entradas - total_saidas)

    logger.info(
        f"Fluxo de caixa gerado: entradas={total_entradas}, saidas={total_saidas}, saldo={saldo_final}"
    )

    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "entries": entradas,
        "total_entradas": float(total_entradas),
        "total_saidas": float(total_saidas),
        "saldo_final": float(saldo_final),
    }
