from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from picpay.domain.models import UserType


def _strip_document(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=120)
    document: str = Field(min_length=11, max_length=20)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    user_type: UserType = UserType.COMMON
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)

    @field_validator("document")
    @classmethod
    def _normalize_doc(cls, value: str) -> str:
        digits = _strip_document(value)
        if len(digits) not in (11, 14):
            raise ValueError("documento deve ter 11 (CPF) ou 14 (CNPJ) digitos")
        return digits


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    document: str
    email: str
    user_type: UserType


class WalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    balance: Decimal
