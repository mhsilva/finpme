"""
Parser de XML de Nota Fiscal Eletrônica (NF-e) brasileira.
Extrai dados de emissão, fornecedor e valores da nota.
"""

import logging
from decimal import Decimal
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# Namespace padrão da NF-e brasileira
NS_NFE = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _texto(elemento, caminho: str, ns: dict) -> str | None:
    """Busca texto de um subelemento XML de forma segura."""
    no = elemento.find(caminho, ns)
    return no.text.strip() if no is not None and no.text else None


def parse_nfe_xml(conteudo: bytes) -> list[dict[str, Any]]:
    """
    Parseia um XML de NF-e brasileira e retorna lista de transações.

    Cada NF-e gera uma transação com:
    - date: data de emissão
    - description: nome do emitente + número da nota
    - amount: valor total da nota (negativo, pois é saída/compra)
    - metadata: CNPJ emitente, número da nota, itens
    """
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise ValueError(f"XML de NF-e inválido: {e}")

    # Tenta encontrar o elemento infNFe (pode estar em diferentes níveis)
    inf_nfe = raiz.find(".//nfe:infNFe", NS_NFE)
    if inf_nfe is None:
        # Tenta sem namespace (NF-e sem declaração de namespace explícita)
        inf_nfe = raiz.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
    if inf_nfe is None:
        raise ValueError("Elemento infNFe não encontrado no XML. Verifique se é uma NF-e válida.")

    # Dados de identificação
    ide = inf_nfe.find("nfe:ide", NS_NFE)
    data_emissao = _texto(ide, "nfe:dhEmi", NS_NFE) or _texto(ide, "nfe:dEmi", NS_NFE)
    numero_nota = _texto(ide, "nfe:nNF", NS_NFE)

    # Data: pega apenas YYYY-MM-DD
    if data_emissao and "T" in data_emissao:
        data_emissao = data_emissao.split("T")[0]

    # Dados do emitente (fornecedor)
    emit = inf_nfe.find("nfe:emit", NS_NFE)
    cnpj_emit = _texto(emit, "nfe:CNPJ", NS_NFE) if emit is not None else None
    nome_emit = _texto(emit, "nfe:xNome", NS_NFE) if emit is not None else "Fornecedor desconhecido"

    # Valor total
    total = inf_nfe.find("nfe:total/nfe:ICMSTot", NS_NFE)
    valor_total = _texto(total, "nfe:vNF", NS_NFE) if total is not None else "0"

    # Itens da nota
    itens = []
    for det in inf_nfe.findall("nfe:det", NS_NFE):
        prod = det.find("nfe:prod", NS_NFE)
        if prod is None:
            continue
        itens.append({
            "codigo": _texto(prod, "nfe:cProd", NS_NFE),
            "descricao": _texto(prod, "nfe:xProd", NS_NFE),
            "quantidade": _texto(prod, "nfe:qCom", NS_NFE),
            "unidade": _texto(prod, "nfe:uCom", NS_NFE),
            "valor_unitario": _texto(prod, "nfe:vUnCom", NS_NFE),
            "valor_total": _texto(prod, "nfe:vProd", NS_NFE),
        })

    descricao = f"NF-e {numero_nota} – {nome_emit}"
    if cnpj_emit:
        descricao += f" (CNPJ: {cnpj_emit})"

    transacao = {
        "id": f"nfe_{numero_nota}_{cnpj_emit}",
        "date": data_emissao,
        "description": descricao,
        "amount": -abs(Decimal(str(valor_total or "0"))),  # Compra = saída = negativo
        "source": "nfe_xml",
        "metadata": {
            "cnpj_emitente": cnpj_emit,
            "nome_emitente": nome_emit,
            "numero_nota": numero_nota,
            "itens": itens,
        },
    }

    logger.info(f"NF-e parseada: nota {numero_nota} de {nome_emit} – R$ {valor_total}")
    return [transacao]
