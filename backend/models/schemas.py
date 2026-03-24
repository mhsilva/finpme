"""
Modelos Pydantic para todas as entidades da plataforma FinPME.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Tenant / Empresa
# ---------------------------------------------------------------------------

class TenantBase(BaseModel):
    name: str
    cnpj: Optional[str] = None
    tax_regime: Optional[str] = None  # simples, presumido, real


class TenantCreate(TenantBase):
    pass


class Tenant(TenantBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Usuário
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str
    full_name: Optional[str] = None
    company_name: str
    cnpj: Optional[str] = None
    tax_regime: Optional[str] = "simples"


class UserLogin(UserBase):
    password: str


class UserResponse(UserBase):
    id: UUID
    tenant: Optional[Tenant] = None
    role: Optional[str] = None


# ---------------------------------------------------------------------------
# Transação financeira
# ---------------------------------------------------------------------------

class TransactionBase(BaseModel):
    date: date
    description: str
    amount: Decimal = Field(description="Positivo = entrada, negativo = saída")
    category: Optional[str] = None
    subcategory: Optional[str] = None
    dre_line: Optional[str] = None
    source: Optional[str] = None  # ofx, nfe_xml, manual, csv


class TransactionCreate(TransactionBase):
    source_file_id: Optional[UUID] = None


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    dre_line: Optional[str] = None
    confirmed: Optional[bool] = None


class Transaction(TransactionBase):
    id: UUID
    tenant_id: UUID
    source_file_id: Optional[UUID] = None
    ai_categorized: bool = False
    ai_confidence: Optional[Decimal] = None
    confirmed: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Arquivo enviado
# ---------------------------------------------------------------------------

class UploadedFileBase(BaseModel):
    filename: str
    file_type: str  # ofx, xml, csv, pdf


class UploadedFile(UploadedFileBase):
    id: UUID
    tenant_id: UUID
    storage_path: Optional[str] = None
    status: str = "pending"  # pending, processing, done, error
    processed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UploadedFileStatus(BaseModel):
    id: UUID
    status: str
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Relatórios
# ---------------------------------------------------------------------------

class DRELine(BaseModel):
    label: str
    value: Decimal
    percentage: Optional[Decimal] = None  # % sobre receita líquida


class DREReport(BaseModel):
    period_start: date
    period_end: date
    receita_bruta: Decimal
    deducoes: Decimal
    receita_liquida: Decimal
    cmv: Decimal
    lucro_bruto: Decimal
    despesa_vendas: Decimal
    despesa_admin: Decimal
    despesa_financeira: Decimal
    total_despesas_operacionais: Decimal
    ebitda: Decimal
    outros: Decimal
    lucro_liquido: Decimal
    # Percentuais sobre receita líquida
    margem_bruta: Optional[Decimal] = None
    margem_ebitda: Optional[Decimal] = None
    margem_liquida: Optional[Decimal] = None


class CashFlowEntry(BaseModel):
    period: str  # data ou semana no formato YYYY-WW
    entradas: Decimal
    saidas: Decimal
    saldo_periodo: Decimal
    saldo_acumulado: Decimal


class CashFlowReport(BaseModel):
    period_start: date
    period_end: date
    entries: list[CashFlowEntry]
    total_entradas: Decimal
    total_saidas: Decimal
    saldo_final: Decimal


# ---------------------------------------------------------------------------
# Chat com IA
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    message: str
    context: Optional[dict] = None  # contexto adicional do frontend


class ChatResponse(BaseModel):
    reply: str
    sources: Optional[list[str]] = None


class HistoryMessage(BaseModel):
    role: str   # "user" ou "assistant"
    content: str


class AgentChatRequest(BaseModel):
    messages: list[HistoryMessage]


# ---------------------------------------------------------------------------
# Plano de contas
# ---------------------------------------------------------------------------

class ChartOfAccountsItem(BaseModel):
    id: UUID
    tenant_id: UUID
    code: Optional[str] = None
    name: str
    parent_id: Optional[UUID] = None
    dre_line: Optional[str] = None
    type: str  # revenue, cost, expense, asset, liability

    class Config:
        from_attributes = True
