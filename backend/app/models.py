from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AccountType(StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class PostingDirection(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class TransactionStatus(StrEnum):
    POSTED = "POSTED"
    REVERSED = "REVERSED"


class AccountCreate(BaseModel):
    code: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9\.\-_]+$")]
    name: Annotated[str, Field(min_length=1, max_length=255)]
    type: AccountType
    currency: Annotated[str, Field(min_length=3, max_length=3, default="EUR")]
    allow_negative: bool = True

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()


class AccountResponse(BaseModel):
    id: int
    code: str
    name: str
    type: AccountType
    currency: str
    allow_negative: bool
    created_at: datetime
    balance: Decimal = Decimal("0.0000")
    total_debit: Decimal = Decimal("0.0000")
    total_credit: Decimal = Decimal("0.0000")

    model_config = ConfigDict(from_attributes=True)


class PostingCreate(BaseModel):
    account_id: int
    direction: PostingDirection
    amount: Annotated[Decimal, Field(gt=Decimal("0"), decimal_places=4)]


class TransactionCreate(BaseModel):
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    posted_at: datetime | None = None
    postings: Annotated[list[PostingCreate], Field(min_length=2)]

    @model_validator(mode="after")
    def validate_double_entry_balance(self) -> "TransactionCreate":
        total_debits = sum(
            (p.amount for p in self.postings if p.direction == PostingDirection.DEBIT),
            Decimal("0"),
        )
        total_credits = sum(
            (p.amount for p in self.postings if p.direction == PostingDirection.CREDIT),
            Decimal("0"),
        )
        if total_debits != total_credits:
            raise ValueError(
                f"Transacción descuadrada: Debe ({total_debits}) != Haber ({total_credits})"
            )
        return self


class PostingResponse(BaseModel):
    id: int
    transaction_id: int
    account_id: int
    account_code: str | None = None
    account_name: str | None = None
    direction: PostingDirection
    amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionResponse(BaseModel):
    id: int
    idempotency_key: str
    description: str
    posted_at: datetime
    status: TransactionStatus
    reversal_of_id: int | None = None
    created_at: datetime
    postings: list[PostingResponse]

    model_config = ConfigDict(from_attributes=True)


class TrialBalanceLine(BaseModel):
    account_id: int
    code: str
    name: str
    type: AccountType
    total_debit: Decimal
    total_credit: Decimal
    debit_balance: Decimal
    credit_balance: Decimal


class TrialBalanceReport(BaseModel):
    as_of: datetime
    lines: list[TrialBalanceLine]
    total_debits: Decimal
    total_credits: Decimal
    total_debit_balance: Decimal
    total_credit_balance: Decimal
    is_balanced: bool


class AccountStatementItem(BaseModel):
    posting_id: int
    transaction_id: int
    posted_at: datetime
    description: str
    direction: PostingDirection
    amount: Decimal
    running_balance: Decimal


class AccountStatementResponse(BaseModel):
    account: AccountResponse
    items: list[AccountStatementItem]
