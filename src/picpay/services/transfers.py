from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from picpay.domain.exceptions import (
    InvalidTransferAmount,
    MerchantCannotSend,
    SameUserTransfer,
    UserNotFound,
)
from picpay.domain.models import NotificationStatus, Transfer, TransferStatus
from picpay.repositories.transfers import TransferRepository
from picpay.repositories.users import UserRepository
from picpay.services.authorizer import Authorizer
from picpay.services.notifier import Notifier

logger = logging.getLogger(__name__)

_TWO_PLACES = Decimal("0.01")


class TransferService:
    def __init__(
        self,
        session: Session,
        users: UserRepository,
        transfers: TransferRepository,
        authorizer: Authorizer,
        notifier: Notifier,
    ) -> None:
        self.session = session
        self.users = users
        self.transfers = transfers
        self.authorizer = authorizer
        self.notifier = notifier

    def transfer(
        self, payer_id: int, payee_id: int, amount: Decimal | float | int | str
    ) -> Transfer:
        amount = self._normalize_amount(amount)
        if payer_id == payee_id:
            raise SameUserTransfer()

        payer = self.users.get(payer_id)
        if payer is None:
            raise UserNotFound(f"pagador {payer_id} nao encontrado")
        payee = self.users.get(payee_id)
        if payee is None:
            raise UserNotFound(f"recebedor {payee_id} nao encontrado")
        if payer.is_merchant:
            raise MerchantCannotSend()

        payer_name = payer.full_name

        # Libera a transacao implicita iniciada pelas leituras: nao queremos
        # segurar conexao/locks durante a chamada HTTP ao autorizador.
        self.session.rollback()

        # Autoriza ANTES de tocar nas carteiras. Negacao ou indisponibilidade
        # do servico externo aborta sem qualquer mutacao financeira.
        self.authorizer.authorize()

        transfer = self._execute_atomic(payer_id, payee_id, amount)

        # Notificacao e best-effort: nao reverte a transferencia em falha.
        ok = self.notifier.notify(
            user_id=payee_id,
            message=f"Voce recebeu R$ {amount} de {payer_name}.",
        )
        transfer.notification_status = (
            NotificationStatus.SENT if ok else NotificationStatus.FAILED
        )
        self.session.commit()
        self.session.refresh(transfer)
        return transfer

    def _execute_atomic(
        self, payer_id: int, payee_id: int, amount: Decimal
    ) -> Transfer:
        with self.session.begin():
            payer_wallet, payee_wallet = self.users.lock_wallets(payer_id, payee_id)
            payer_wallet.debit(amount)
            payee_wallet.credit(amount)

            transfer = Transfer(
                payer_id=payer_id,
                payee_id=payee_id,
                amount=amount,
                status=TransferStatus.PENDING,
                notification_status=NotificationStatus.PENDING,
            )
            self.transfers.add(transfer)
            transfer.mark_completed()
        return transfer

    @staticmethod
    def _normalize_amount(value: Decimal | float | int | str) -> Decimal:
        try:
            amount = Decimal(str(value)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        except (ArithmeticError, ValueError) as exc:
            raise InvalidTransferAmount("valor invalido") from exc
        if amount <= 0:
            raise InvalidTransferAmount()
        return amount
