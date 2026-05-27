from __future__ import annotations

from fastapi import APIRouter, Depends, status

from picpay.api.deps import transfer_service
from picpay.schemas.transfers import TransferRequest, TransferResponse
from picpay.services.transfers import TransferService

router = APIRouter(tags=["transfers"])


@router.post(
    "/transfer",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Realiza uma transferencia entre usuarios",
)
def create_transfer(
    payload: TransferRequest,
    service: TransferService = Depends(transfer_service),
) -> TransferResponse:
    transfer = service.transfer(
        payer_id=payload.payer,
        payee_id=payload.payee,
        amount=payload.value,
    )
    return TransferResponse.model_validate(transfer)
