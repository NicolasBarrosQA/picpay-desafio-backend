from __future__ import annotations

from sqlalchemy.orm import Session

from picpay.domain.models import Transfer


class TransferRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, transfer: Transfer) -> Transfer:
        self.session.add(transfer)
        self.session.flush()
        return transfer

    def get(self, transfer_id: int) -> Transfer | None:
        return self.session.get(Transfer, transfer_id)
