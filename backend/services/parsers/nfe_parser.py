"""
Parser de XML de Nota Fiscal Eletrônica (NF-e) brasileira.

Gera uma conta a pagar ou a receber (payable/receivable), não uma transaction.
O dinheiro só vira lançamento quando o pagamento acontecer (via OFX/conciliação).

Tipos:
  tpNF = 0 → entrada (compra) → payable   (tenho que pagar ao fornecedor)
  tpNF = 1 → saída  (venda)  → receivable (cliente vai me pagar)
"""

import logging
from decimal import Decimal
from typing import Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

NS_NFE = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def _texto(elemento, caminho: str, ns: dict) -> str | None:
    no = elemento.find(caminho, ns)
    return no.text.strip() if no is not None and no.text else None


def parse_nfe_xml(conteudo: bytes) -> list[dict[str, Any]]:
    """
    Parseia NF-e e retorna lista com UMA entrada no formato payable/receivable.

    Campos retornados:
      type, description, amount, due_date, contact_name, contact_doc,
      notes, source (='nfe_xml'), _nfe_metadata
    """
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        raise ValueError(f"XML de NF-e inválido: {e}")

    inf_nfe = raiz.find(".//nfe:infNFe", NS_NFE)
    if inf_nfe is None:
        inf_nfe = raiz.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
    if inf_nfe is None:
        raise ValueError("Elemento infNFe não encontrado. Verifique se é uma NF-e válida.")

    # ── Identificação ──────────────────────────────────────────────────────
    ide         = inf_nfe.find("nfe:ide", NS_NFE)
    numero_nota = _texto(ide, "nfe:nNF", NS_NFE)
    serie       = _texto(ide, "nfe:serie", NS_NFE)
    tp_nf       = _texto(ide, "nfe:tpNF", NS_NFE)   # "0" entrada / "1" saída
    data_emissao = _texto(ide, "nfe:dhEmi", NS_NFE) or _texto(ide, "nfe:dEmi", NS_NFE)
    if data_emissao and "T" in data_emissao:
        data_emissao = data_emissao.split("T")[0]

    # ── Emitente ───────────────────────────────────────────────────────────
    emit      = inf_nfe.find("nfe:emit", NS_NFE)
    cnpj_emit = _texto(emit, "nfe:CNPJ", NS_NFE) if emit is not None else None
    nome_emit = _texto(emit, "nfe:xNome", NS_NFE) if emit is not None else "Fornecedor desconhecido"

    # ── Destinatário ───────────────────────────────────────────────────────
    dest      = inf_nfe.find("nfe:dest", NS_NFE)
    cnpj_dest = (_texto(dest, "nfe:CNPJ", NS_NFE) or _texto(dest, "nfe:CPF", NS_NFE)) if dest is not None else None
    nome_dest = _texto(dest, "nfe:xNome", NS_NFE) if dest is not None else None

    # ── Valor total ────────────────────────────────────────────────────────
    total_el  = inf_nfe.find("nfe:total/nfe:ICMSTot", NS_NFE)
    valor_str = _texto(total_el, "nfe:vNF", NS_NFE) if total_el is not None else "0"
    valor     = abs(Decimal(str(valor_str or "0")))

    # ── Data de vencimento (duplicatas) ────────────────────────────────────
    # Tenta extrair do bloco de cobrança/duplicatas (cobr/dup/dvenc)
    due_date = data_emissao  # fallback: data de emissão
    cobr = inf_nfe.find("nfe:cobr", NS_NFE)
    if cobr is not None:
        dups = cobr.findall("nfe:dup", NS_NFE)
        if dups:
            # Pega o vencimento da primeira duplicata
            dvenc = _texto(dups[0], "nfe:dvenc", NS_NFE)
            if dvenc:
                due_date = dvenc

    # ── Itens ──────────────────────────────────────────────────────────────
    itens = []
    for det in inf_nfe.findall("nfe:det", NS_NFE):
        prod = det.find("nfe:prod", NS_NFE)
        if prod is None:
            continue
        itens.append({
            "descricao":      _texto(prod, "nfe:xProd", NS_NFE),
            "quantidade":     _texto(prod, "nfe:qCom", NS_NFE),
            "unidade":        _texto(prod, "nfe:uCom", NS_NFE),
            "valor_unitario": _texto(prod, "nfe:vUnCom", NS_NFE),
            "valor_total":    _texto(prod, "nfe:vProd", NS_NFE),
        })

    # ── Tipo P/R ───────────────────────────────────────────────────────────
    # tpNF=0 entrada → payable (devo pagar ao emitente)
    # tpNF=1 saída   → receivable (destinatário me deve)
    is_entrada   = (tp_nf == "0")
    pr_type      = "payable" if is_entrada else "receivable"
    contact_name = nome_emit if is_entrada else (nome_dest or "Cliente desconhecido")
    contact_doc  = cnpj_emit if is_entrada else cnpj_dest

    num_label = f"NF-e {serie}-{numero_nota}" if serie else f"NF-e {numero_nota}"
    description = f"{num_label} – {contact_name}"

    itens_resumo = "; ".join(
        i["descricao"] for i in itens[:3] if i.get("descricao")
    )
    notes = f"Itens: {itens_resumo}" if itens_resumo else None

    resultado = {
        "type":         pr_type,
        "description":  description,
        "amount":       valor,
        "due_date":     due_date,
        "contact_name": contact_name,
        "contact_doc":  contact_doc,
        "notes":        notes,
        "source":       "nfe_xml",
        "_nfe_metadata": {
            "numero_nota":   numero_nota,
            "serie":         serie,
            "cnpj_emitente": cnpj_emit,
            "nome_emitente": nome_emit,
            "cnpj_dest":     cnpj_dest,
            "nome_dest":     nome_dest,
            "tp_nf":         tp_nf,
            "itens":         itens,
        },
    }

    logger.info(f"NF-e parseada: {num_label} | {pr_type} | {contact_name} | R$ {valor}")
    return [resultado]
