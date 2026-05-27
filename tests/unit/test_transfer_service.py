from __future__ import annotations

from decimal import Decimal

import pytest

from picpay.domain.exceptions import (
    AuthorizerUnavailable,
    InsufficientFunds,
    InvalidTransferAmount,
    MerchantCannotSend,
    SameUserTransfer,
    TransferNotAuthorized,
    UserNotFound,
)
from picpay.domain.models import NotificationStatus, TransferStatus, UserType
from picpay.repositories.transfers import TransferRepository
from picpay.repositories.users import UserRepository
from picpay.services.transfers import TransferService
from tests.conftest import FakeAuthorizer, FakeNotifier


def _service(session, authorizer=None, notifier=None) -> TransferService:
    return TransferService(
        session=session,
        users=UserRepository(session),
        transfers=TransferRepository(session),
        authorizer=authorizer or FakeAuthorizer(),
        notifier=notifier or FakeNotifier(),
    )


def test_transferencia_feliz_debita_e_credita(session, seed_users):
    payer, payee = seed_users(payer_balance=Decimal("100.00"))
    svc = _service(session)

    transfer = svc.transfer(payer.id, payee.id, Decimal("30.00"))

    session.refresh(payer)
    session.refresh(payee)
    assert payer.wallet.balance == Decimal("70.00")
    assert payee.wallet.balance == Decimal("30.00")
    assert transfer.status == TransferStatus.COMPLETED
    assert transfer.notification_status == NotificationStatus.SENT
    assert transfer.completed_at is not None


def test_pagador_lojista_e_proibido(session, seed_users):
    payer, payee = seed_users(payer_type=UserType.MERCHANT)
    svc = _service(session)
    with pytest.raises(MerchantCannotSend):
        svc.transfer(payer.id, payee.id, Decimal("10.00"))


def test_saldo_insuficiente_aborta(session, seed_users):
    payer, payee = seed_users(payer_balance=Decimal("5.00"))
    svc = _service(session)
    with pytest.raises(InsufficientFunds):
        svc.transfer(payer.id, payee.id, Decimal("10.00"))
    session.refresh(payer)
    session.refresh(payee)
    assert payer.wallet.balance == Decimal("5.00")
    assert payee.wallet.balance == Decimal("0.00")


def test_autorizador_negando_nao_movimenta_carteiras(session, seed_users):
    payer, payee = seed_users()
    svc = _service(session, authorizer=FakeAuthorizer(authorized=False))
    with pytest.raises(TransferNotAuthorized):
        svc.transfer(payer.id, payee.id, Decimal("10.00"))
    session.refresh(payer)
    session.refresh(payee)
    assert payer.wallet.balance == Decimal("100.00")
    assert payee.wallet.balance == Decimal("0.00")


def test_autorizador_indisponivel_propaga(session, seed_users):
    payer, payee = seed_users()
    svc = _service(session, authorizer=FakeAuthorizer(raise_unavailable=True))
    with pytest.raises(AuthorizerUnavailable):
        svc.transfer(payer.id, payee.id, Decimal("10.00"))


def test_falha_de_notificacao_nao_reverte_transferencia(session, seed_users):
    payer, payee = seed_users()
    notifier = FakeNotifier(ok=False)
    svc = _service(session, notifier=notifier)

    transfer = svc.transfer(payer.id, payee.id, Decimal("10.00"))

    assert transfer.status == TransferStatus.COMPLETED
    assert transfer.notification_status == NotificationStatus.FAILED
    session.refresh(payer)
    session.refresh(payee)
    assert payer.wallet.balance == Decimal("90.00")
    assert payee.wallet.balance == Decimal("10.00")


def test_payer_igual_payee_invalido(session, seed_users):
    payer, _ = seed_users()
    svc = _service(session)
    with pytest.raises(SameUserTransfer):
        svc.transfer(payer.id, payer.id, Decimal("1.00"))


def test_valor_zero_ou_negativo_invalido(session, seed_users):
    payer, payee = seed_users()
    svc = _service(session)
    with pytest.raises(InvalidTransferAmount):
        svc.transfer(payer.id, payee.id, Decimal("0"))
    with pytest.raises(InvalidTransferAmount):
        svc.transfer(payer.id, payee.id, Decimal("-5"))


def test_usuario_inexistente(session, seed_users):
    payer, _ = seed_users()
    svc = _service(session)
    with pytest.raises(UserNotFound):
        svc.transfer(payer.id, 9999, Decimal("1.00"))
    with pytest.raises(UserNotFound):
        svc.transfer(9999, payer.id, Decimal("1.00"))


def test_valor_e_arredondado_para_duas_casas(session, seed_users):
    payer, payee = seed_users(payer_balance=Decimal("100.00"))
    svc = _service(session)
    transfer = svc.transfer(payer.id, payee.id, Decimal("10.005"))
    assert transfer.amount == Decimal("10.01")
