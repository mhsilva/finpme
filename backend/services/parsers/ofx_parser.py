"""
Parser de arquivos OFX (Open Financial Exchange).
Extrai transações bancárias de extratos no formato OFX/QFX.
"""

import io
import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def parse_ofx(conteudo: bytes) -> list[dict[str, Any]]:
    """
    Parseia um arquivo OFX e retorna lista de transações normalizadas.

    Cada transação contém:
    - id: identificador único da transação
    - date: data no formato YYYY-MM-DD (string)
    - description: descrição/histórico
    - amount: valor (Decimal, positivo = crédito, negativo = débito)
    """
    try:
        from ofxparse import OfxParser
    except ImportError:
        raise RuntimeError("Biblioteca ofxparse não instalada. Execute: pip install ofxparse")

    try:
        arquivo = io.BytesIO(conteudo)
        ofx = OfxParser.parse(arquivo)
    except Exception as e:
        logger.error(f"Erro ao parsear OFX: {e}")
        raise ValueError(f"Arquivo OFX inválido ou corrompido: {e}")

    transacoes = []

    for conta in ofx.accounts if hasattr(ofx, "accounts") else [ofx.account]:
        if conta is None or not hasattr(conta, "statement"):
            continue
        statement = conta.statement
        if statement is None:
            continue

        for transacao in statement.transactions:
            try:
                data_str = transacao.date.strftime("%Y-%m-%d") if transacao.date else None
                if not data_str:
                    continue

                transacoes.append({
                    "id": str(transacao.id) if transacao.id else None,
                    "date": data_str,
                    "description": str(transacao.memo or transacao.payee or "Sem descrição").strip(),
                    "amount": Decimal(str(transacao.amount)),
                    "source": "ofx",
                })
            except Exception as e:
                logger.warning(f"Erro ao processar transação OFX: {e} – pulando")
                continue

    logger.info(f"OFX parseado: {len(transacoes)} transações extraídas")
    return transacoes
