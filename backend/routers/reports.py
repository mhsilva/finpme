"""
Router de relatórios financeiros.
Retorna DRE e Fluxo de Caixa com cache Redis.
"""

import json
import logging
import os
from datetime import date

from fastapi import APIRouter, HTTPException, Request, status

from services.cashflow_generator import generate_cashflow
from services.dre_generator import generate_dre

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Cache Redis
# Suporta dois modos:
#   - Local (dev): UPSTASH_REDIS_URL=redis://localhost:6379  (sem token)
#   - Produção:    UPSTASH_REDIS_URL=https://...upstash.io   (com token)
# ---------------------------------------------------------------------------
_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        url = os.environ.get("UPSTASH_REDIS_URL", "")
        token = os.environ.get("UPSTASH_REDIS_TOKEN", "")

        if not url:
            return None

        try:
            if url.startswith("redis://") or url.startswith("rediss://"):
                # Modo local: usa redis-py diretamente
                import redis as redis_py
                cliente = redis_py.from_url(url, decode_responses=True)
                cliente.ping()  # verifica conexão

                # Cria wrapper com mesma interface de get/setex
                class _RedisLocalWrapper:
                    def get(self, k):       return cliente.get(k)
                    def setex(self, k, t, v): return cliente.setex(k, t, v)

                _redis = _RedisLocalWrapper()
            else:
                # Modo Upstash (produção)
                from upstash_redis import Redis
                _redis = Redis(url=url, token=token)

        except Exception as e:
            logger.warning(f"Redis não disponível, cache desativado: {e}")

    return _redis


def _cache_get(chave: str):
    redis = _get_redis()
    if not redis:
        return None
    try:
        valor = redis.get(chave)
        return json.loads(valor) if valor else None
    except Exception as e:
        logger.warning(f"Erro ao ler cache Redis: {e}")
        return None


def invalidar_cache_tenant(tenant_id: str):
    """Invalida cache de DRE e cashflow para o tenant nos últimos 6 meses."""
    redis = _get_redis()
    if not redis:
        return
    try:
        from datetime import date as _date
        hoje = _date.today()
        for i in range(6):
            mes = hoje.month - i
            ano = hoje.year
            while mes <= 0:
                mes += 12
                ano -= 1
            inicio = f"{ano}-{mes:02d}-01"
            fim_dia = [31,28,31,30,31,30,31,31,30,31,30,31][mes - 1]
            fim = f"{ano}-{mes:02d}-{fim_dia:02d}"
            redis.delete(f"dre:{tenant_id}:{inicio}:{fim}")
            redis.delete(f"cashflow:{tenant_id}:{inicio}:{fim}")
    except Exception as e:
        logger.warning(f"Erro ao invalidar cache: {e}")


def _cache_set(chave: str, valor: dict, ttl_segundos: int = 3600):
    redis = _get_redis()
    if not redis:
        return
    try:
        redis.setex(chave, ttl_segundos, json.dumps(valor, default=str))
    except Exception as e:
        logger.warning(f"Erro ao salvar cache Redis: {e}")


@router.get("/dre")
async def relatorio_dre(
    request: Request,
    start: str,
    end: str,
):
    """
    Retorna o DRE (Demonstração de Resultado do Exercício) do período.
    Datas no formato YYYY-MM-DD.
    Usa cache Redis com TTL de 1 hora.
    """
    tenant_id: str = request.state.tenant_id

    try:
        inicio = date.fromisoformat(start)
        fim = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datas devem estar no formato YYYY-MM-DD",
        )

    chave_cache = f"dre:{tenant_id}:{start}:{end}"
    cached = _cache_get(chave_cache)
    if cached:
        logger.info(f"DRE servido do cache para tenant {tenant_id}")
        return cached

    try:
        dre = generate_dre(tenant_id, inicio, fim)
    except Exception as e:
        logger.error(f"Erro ao gerar DRE: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar relatório DRE",
        )

    _cache_set(chave_cache, dre)
    return dre


@router.get("/cashflow")
async def relatorio_fluxo_caixa(
    request: Request,
    start: str,
    end: str,
):
    """
    Retorna o Fluxo de Caixa do período agrupado por semana.
    Datas no formato YYYY-MM-DD.
    Usa cache Redis com TTL de 1 hora.
    """
    tenant_id: str = request.state.tenant_id

    try:
        inicio = date.fromisoformat(start)
        fim = date.fromisoformat(end)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Datas devem estar no formato YYYY-MM-DD",
        )

    chave_cache = f"cashflow:{tenant_id}:{start}:{end}"
    cached = _cache_get(chave_cache)
    if cached:
        logger.info(f"Fluxo de caixa servido do cache para tenant {tenant_id}")
        return cached

    try:
        cashflow = generate_cashflow(tenant_id, inicio, fim)
    except Exception as e:
        logger.error(f"Erro ao gerar fluxo de caixa: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar relatório de fluxo de caixa",
        )

    _cache_set(chave_cache, cashflow)
    return cashflow
