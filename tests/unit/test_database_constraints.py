from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from picpay.domain.models import NotificationStatus, Transfer, TransferStatus


def test_wallet_nao_aceita_saldo_negativo(session, seed_users):
    payer, _ = seed_users()
    payer.wallet.balance = Decimal("-0.01")

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_transfer_nao_aceita_valor_zero(session, seed_users):
    payer, payee = seed_users()
    session.add(
        Transfer(
            payer_id=payer.id,
            payee_id=payee.id,
            amount=Decimal("0.00"),
            status=TransferStatus.COMPLETED,
            notification_status=NotificationStatus.SENT,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_transfer_nao_aceita_mesmo_pagador_e_recebedor(session, seed_users):
    payer, _ = seed_users()
    session.add(
        Transfer(
            payer_id=payer.id,
            payee_id=payer.id,
            amount=Decimal("1.00"),
            status=TransferStatus.COMPLETED,
            notification_status=NotificationStatus.SENT,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
