from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends
from sqlalchemy.orm import Session

from picpay.config import Settings, get_settings
from picpay.db import get_session
from picpay.repositories.transfers import TransferRepository
from picpay.repositories.users import UserRepository
from picpay.services.authorizer import Authorizer, HttpAuthorizer
from picpay.services.notifier import HttpNotifier, Notifier
from picpay.services.transfers import TransferService


def db_session() -> Iterator[Session]:
    yield from get_session()


def settings_dep() -> Settings:
    return get_settings()


def user_repository(session: Session = Depends(db_session)) -> UserRepository:
    return UserRepository(session)


def transfer_repository(session: Session = Depends(db_session)) -> TransferRepository:
    return TransferRepository(session)


def authorizer_service(settings: Settings = Depends(settings_dep)) -> Authorizer:
    return HttpAuthorizer(settings)


def notifier_service(settings: Settings = Depends(settings_dep)) -> Notifier:
    return HttpNotifier(settings)


def transfer_service(
    session: Session = Depends(db_session),
    users: UserRepository = Depends(user_repository),
    transfers: TransferRepository = Depends(transfer_repository),
    authorizer: Authorizer = Depends(authorizer_service),
    notifier: Notifier = Depends(notifier_service),
) -> TransferService:
    return TransferService(
        session=session,
        users=users,
        transfers=transfers,
        authorizer=authorizer,
        notifier=notifier,
    )
