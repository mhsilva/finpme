"""
Parser de arquivos CSV de extratos bancários.
Detecta separador automaticamente e mapeia colunas com nomes comuns.
"""

import csv
import io
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

# Mapeamento de nomes de colunas comuns para os campos internos
MAPA_COLUNAS_DATA = {"data", "date", "dt", "data_lancamento", "datalancamento", "data_movimento"}
MAPA_COLUNAS_VALOR = {"valor", "value", "amount", "vlr", "vl", "vl_lancamento", "credito_debito"}
MAPA_COLUNAS_DESCRICAO = {
    "descricao", "description", "historico", "memo", "complemento",
    "descr", "historico_lancamento", "desc",
}


def _detectar_separador(conteudo_texto: str) -> str:
    """Detecta o separador CSV mais provável (vírgula ou ponto-e-vírgula)."""
    amostra = "\n".join(conteudo_texto.splitlines()[:5])
    contagem_ponto_virgula = amostra.count(";")
    contagem_virgula = amostra.count(",")
    return ";" if contagem_ponto_virgula > contagem_virgula else ","


def _normalizar_coluna(nome: str) -> str:
    """Normaliza nome de coluna: minúsculas, sem espaços/acentos."""
    import unicodedata
    nome = nome.lower().strip()
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = nome.replace(" ", "_").replace("-", "_")
    return nome


def _parsear_valor(valor_str: str) -> Decimal:
    """
    Converte string de valor monetário para Decimal.
    Suporta formatos: 1.234,56 | 1234.56 | -1.234,56
    """
    if not valor_str:
        return Decimal("0")

    valor = valor_str.strip().replace("R$", "").replace(" ", "")

    # Formato brasileiro: 1.234,56
    if "," in valor and "." in valor:
        valor = valor.replace(".", "").replace(",", ".")
    elif "," in valor:
        # Pode ser separador decimal (1234,56) ou milhar mal formatado
        partes = valor.split(",")
        if len(partes) == 2 and len(partes[1]) <= 2:
            valor = valor.replace(",", ".")
        else:
            valor = valor.replace(",", "")

    try:
        return Decimal(valor)
    except InvalidOperation:
        raise ValueError(f"Não foi possível converter '{valor_str}' para valor numérico")


def _parsear_data(data_str: str) -> str:
    """
    Converte string de data para o formato YYYY-MM-DD.
    Tenta os formatos mais comuns.
    """
    from datetime import datetime

    formatos = [
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y",
        "%Y/%m/%d", "%m/%d/%Y", "%d.%m.%Y",
    ]
    data_str = data_str.strip()
    for fmt in formatos:
        try:
            return datetime.strptime(data_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(f"Formato de data não reconhecido: '{data_str}'")


def parse_csv(conteudo: bytes) -> list[dict[str, Any]]:
    """
    Parseia um arquivo CSV de extrato bancário.

    Detecta separador automaticamente e tenta mapear colunas com nomes comuns.
    Retorna lista de transações normalizadas.
    """
    # Tenta decodificar com encodings comuns
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            texto = conteudo.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Não foi possível decodificar o arquivo CSV. Verifique o encoding.")

    separador = _detectar_separador(texto)
    leitor = csv.DictReader(io.StringIO(texto), delimiter=separador)

    if not leitor.fieldnames:
        raise ValueError("CSV vazio ou sem cabeçalho")

    # Mapeia colunas encontradas para os campos internos
    colunas_normalizadas = {_normalizar_coluna(c): c for c in leitor.fieldnames}

    col_data = next((colunas_normalizadas[c] for c in colunas_normalizadas if c in MAPA_COLUNAS_DATA), None)
    col_valor = next((colunas_normalizadas[c] for c in colunas_normalizadas if c in MAPA_COLUNAS_VALOR), None)
    col_descricao = next(
        (colunas_normalizadas[c] for c in colunas_normalizadas if c in MAPA_COLUNAS_DESCRICAO), None
    )

    if not col_data or not col_valor:
        colunas_disponiveis = list(colunas_normalizadas.keys())
        raise ValueError(
            f"Colunas obrigatórias 'data' e 'valor' não encontradas. "
            f"Colunas disponíveis: {colunas_disponiveis}"
        )

    transacoes = []
    erros = 0

    for i, linha in enumerate(leitor, start=2):
        try:
            data = _parsear_data(linha[col_data])
            valor = _parsear_valor(linha[col_valor])
            descricao = linha[col_descricao].strip() if col_descricao else f"Lançamento linha {i}"

            transacoes.append({
                "id": f"csv_linha_{i}",
                "date": data,
                "description": descricao,
                "amount": valor,
                "source": "csv",
            })
        except Exception as e:
            logger.warning(f"Erro na linha {i} do CSV: {e} – pulando")
            erros += 1
            continue

    logger.info(f"CSV parseado: {len(transacoes)} transações extraídas, {erros} erros ignorados")
    return transacoes
