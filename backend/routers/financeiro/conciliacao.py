"""
Conciliação Bancária — algoritmo de auto-match e confirmação manual.

Fluxo:
  1. GET /sugestoes  → algoritmo compara transactions × payables_receivables e retorna pares com score
  2. POST /confirmar → usuário aprova um par (cria reconciliation_match + marca payable como pago)
  3. POST /auto      → confirma automaticamente todos os pares com score >= threshold
  4. DELETE /{id}    → desfaz uma conciliação confirmada
"""

import logging
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from db.supabase import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Algoritmo de score
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> set[str]:
    """Remove pontuação, converte para minúsculas, retorna conjunto de palavras."""
    limpo = re.sub(r"[^\w\s]", " ", texto.lower())
    return {w for w in limpo.split() if len(w) > 2}


def _calcular_score(tx: dict, pr: dict) -> float:
    """
    Score de 0.0 a 1.0 entre uma transação e uma conta P/R.

    Composição:
      - Valor   (50%): quão próximos são os valores absolutos
      - Data    (30%): diferença em dias entre data da tx e vencimento
      - Descrição (20%): sobreposição de palavras (Jaccard simplificado)
    """
    score = 0.0

    # 1. Valor
    tx_val = abs(float(tx["amount"]))
    pr_val = abs(float(pr["amount"]))
    if pr_val > 0:
        diff_pct = abs(tx_val - pr_val) / pr_val
        if diff_pct < 0.001:
            score += 0.50
        elif diff_pct < 0.01:
            score += 0.35
        elif diff_pct < 0.05:
            score += 0.15

    # 2. Data
    try:
        tx_date = date.fromisoformat(tx["date"])
        pr_date = date.fromisoformat(pr["due_date"])
        diff_dias = abs((tx_date - pr_date).days)
        if diff_dias == 0:
            score += 0.30
        elif diff_dias <= 2:
            score += 0.22
        elif diff_dias <= 5:
            score += 0.12
        elif diff_dias <= 10:
            score += 0.05
    except Exception:
        pass

    # 3. Descrição
    tx_words = _normalizar(tx.get("description", ""))
    pr_words = _normalizar(pr.get("description", ""))
    if tx_words and pr_words:
        intersecao = len(tx_words & pr_words)
        uniao      = len(tx_words | pr_words)
        jaccard    = intersecao / uniao if uniao > 0 else 0
        score += min(0.20, jaccard * 0.40)

    return round(min(score, 1.0), 3)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/stats")
def stats_conciliacao(request: Request):
    """Resumo: quantas transações estão conciliadas, pendentes e total."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    total_tx_res = (
        client.table("transactions")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    conciliadas_res = (
        client.table("reconciliation_matches")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    total       = total_tx_res.count or 0
    conciliadas = conciliadas_res.count or 0

    return {
        "total_transacoes":  total,
        "conciliadas":       conciliadas,
        "nao_conciliadas":   total - conciliadas,
        "pct_conciliado":    round((conciliadas / total * 100) if total > 0 else 0, 1),
    }


@router.get("/pendentes")
def transacoes_pendentes(
    request: Request,
    inicio: Optional[str] = Query(None),
    fim:    Optional[str] = Query(None),
    limite: int = Query(100, le=500),
):
    """Transações importadas ainda sem conciliação."""
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    # IDs já conciliados
    match_res = (
        client.table("reconciliation_matches")
        .select("transaction_id")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    ids_conciliados = {m["transaction_id"] for m in (match_res.data or [])}

    query = (
        client.table("transactions")
        .select("id, date, description, amount, category, source")
        .eq("tenant_id", tenant_id)
        .eq("confirmed", True)
        .order("date", desc=True)
        .limit(limite)
    )
    if inicio:
        query = query.gte("date", inicio)
    if fim:
        query = query.lte("date", fim)

    res = query.execute()
    todas = res.data or []

    return [t for t in todas if t["id"] not in ids_conciliados]


@router.get("/sugestoes")
def sugestoes_conciliacao(
    request: Request,
    transaction_id: Optional[str] = Query(None, description="Filtrar sugestões para uma tx específica"),
    score_min: float = Query(0.40, description="Score mínimo para retornar sugestão"),
    limite: int = Query(50, le=200),
):
    """
    Roda o algoritmo de matching e retorna pares (transação × conta P/R) com score de confiança.
    Ignora transações já conciliadas e contas já pagas/canceladas.
    """
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    # IDs já conciliados
    match_res = (
        client.table("reconciliation_matches")
        .select("transaction_id")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    ids_conciliados = {m["transaction_id"] for m in (match_res.data or [])}

    # Busca transações
    if transaction_id:
        tx_res = (
            client.table("transactions")
            .select("id, date, description, amount, category, source")
            .eq("id", transaction_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
    else:
        tx_res = (
            client.table("transactions")
            .select("id, date, description, amount, category, source")
            .eq("tenant_id", tenant_id)
            .order("date", desc=True)
            .limit(200)
            .execute()
        )
    transacoes = [t for t in (tx_res.data or []) if t["id"] not in ids_conciliados]

    # Busca contas P/R pendentes / vencidas (não pagas)
    pr_res = (
        client.table("payables_receivables")
        .select("id, type, description, amount, due_date, contact_name, status")
        .eq("tenant_id", tenant_id)
        .in_("status", ["pending", "overdue", "partial"])
        .is_("transaction_id", "null")
        .order("due_date")
        .limit(500)
        .execute()
    )
    contas = pr_res.data or []

    if not transacoes or not contas:
        return []

    sugestoes = []
    for tx in transacoes:
        tx_val = float(tx["amount"])
        # Filtra direção: tx negativa → payable, tx positiva → receivable
        tipo_esperado = "payable" if tx_val < 0 else "receivable"
        candidatas = [c for c in contas if c["type"] == tipo_esperado]

        for pr in candidatas:
            score = _calcular_score(tx, pr)
            if score >= score_min:
                sugestoes.append({
                    "score":       score,
                    "transacao":   tx,
                    "conta":       pr,
                })

    # Ordena por score desc, limita resultado
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes[:limite]


@router.post("/confirmar", status_code=201)
def confirmar_match(
    request: Request,
    transaction_id: str = Query(...),
    payable_receivable_id: str = Query(...),
    matched_by: str = Query("manual"),
):
    """
    Confirma um par (transação ↔ conta P/R):
      - Cria registro em reconciliation_matches
      - Marca a conta P/R como paga e vincula a transaction_id
      - Atualiza confirmed=True na transação
    """
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    # Valida transação
    tx_res = (
        client.table("transactions")
        .select("id, amount, date")
        .eq("id", transaction_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not tx_res.data:
        raise HTTPException(status_code=404, detail="Transação não encontrada")

    # Valida conta P/R
    pr_res = (
        client.table("payables_receivables")
        .select("id, amount, status")
        .eq("id", payable_receivable_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not pr_res.data:
        raise HTTPException(status_code=404, detail="Conta não encontrada")

    # Calcula score para registrar
    tx = tx_res.data
    pr = pr_res.data
    score = _calcular_score(
        {**tx, "description": ""},
        {**pr, "description": "", "due_date": pr_res.data.get("due_date", tx["date"])},
    )

    # Insere match
    try:
        match_res = (
            client.table("reconciliation_matches")
            .insert({
                "tenant_id":             tenant_id,
                "transaction_id":        transaction_id,
                "payable_receivable_id": payable_receivable_id,
                "matched_by":            matched_by,
                "confidence":            score,
            })
            .execute()
        )
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Transação já conciliada")
        raise

    # Marca conta P/R como paga + vincula tx
    client.table("payables_receivables").update({
        "status":         "paid",
        "paid_date":      tx["date"],
        "transaction_id": transaction_id,
    }).eq("id", payable_receivable_id).eq("tenant_id", tenant_id).execute()

    # Marca transação como confirmada
    client.table("transactions").update({"confirmed": True}).eq(
        "id", transaction_id
    ).eq("tenant_id", tenant_id).execute()

    return match_res.data[0]


@router.post("/auto")
def auto_conciliar(
    request: Request,
    score_min: float = Query(0.80, description="Score mínimo para auto-confirmar"),
):
    """
    Confirma automaticamente todos os pares com score >= score_min.
    Retorna quantos matches foram criados.
    """
    tenant_id = request.state.tenant_id

    # Reutiliza a lógica de sugestões
    class _FakeRequest:
        state = type("S", (), {"tenant_id": tenant_id})()

    sugestoes = sugestoes_conciliacao(
        _FakeRequest(), transaction_id=None, score_min=score_min, limite=200
    )

    # Evita duplicatas: uma tx só pode ser confirmada uma vez
    confirmados = []
    tx_usadas: set[str] = set()
    pr_usadas: set[str] = set()

    for s in sugestoes:
        tx_id = s["transacao"]["id"]
        pr_id = s["conta"]["id"]
        if tx_id in tx_usadas or pr_id in pr_usadas:
            continue
        try:
            class _FR:
                state = type("S", (), {"tenant_id": tenant_id})()
            confirmar_match(_FR(), transaction_id=tx_id, payable_receivable_id=pr_id, matched_by="auto")
            confirmados.append({"transaction_id": tx_id, "payable_receivable_id": pr_id, "score": s["score"]})
            tx_usadas.add(tx_id)
            pr_usadas.add(pr_id)
        except Exception as e:
            logger.warning(f"Auto-match falhou tx={tx_id} pr={pr_id}: {e}")

    return {
        "confirmados": len(confirmados),
        "matches":     confirmados,
    }


@router.delete("/{match_id}", status_code=204)
def desfazer_conciliacao(match_id: str, request: Request):
    """
    Desfaz uma conciliação: remove o match e reverte a conta P/R para 'pending'.
    """
    tenant_id = request.state.tenant_id
    client = get_supabase_client()

    match_res = (
        client.table("reconciliation_matches")
        .select("*")
        .eq("id", match_id)
        .eq("tenant_id", tenant_id)
        .single()
        .execute()
    )
    if not match_res.data:
        raise HTTPException(status_code=404, detail="Match não encontrado")

    m = match_res.data

    # Remove match
    client.table("reconciliation_matches").delete().eq("id", match_id).execute()

    # Reverte conta P/R
    if m.get("payable_receivable_id"):
        client.table("payables_receivables").update({
            "status":         "pending",
            "paid_date":      None,
            "transaction_id": None,
        }).eq("id", m["payable_receivable_id"]).eq("tenant_id", tenant_id).execute()

    # Reverte confirmed da transação
    if m.get("transaction_id"):
        client.table("transactions").update({"confirmed": False}).eq(
            "id", m["transaction_id"]
        ).eq("tenant_id", tenant_id).execute()
