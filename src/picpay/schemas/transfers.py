from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from picpay.domain.models import NotificationStatus, TransferStatus


class TransferRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Decimal = Field(gt=0, description="Valor da transferencia em reais")
    payer: int = Field(gt=0, description="ID do usuario pagador")
    payee: int = Field(gt=0, description="ID do usuario recebedor")


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payer_id: int
    payee_id: int
    amount: Decimal
    status: TransferStatus
    notification_status: NotificationStatus
    created_at: datetime
    completed_at: datetime | None = None
