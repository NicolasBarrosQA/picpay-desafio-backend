from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from picpay.api.deps import authorizer_service, db_session, notifier_service
from picpay.db import Base
from picpay.domain.models import User, UserType, Wallet
from picpay.main import create_app
from picpay.services.authorizer import Authorizer
from picpay.services.notifier import Notifier


class FakeAuthorizer:
    def __init__(self, authorized: bool = True, raise_unavailable: bool = False):
        self.authorized = authorized
        self.raise_unavailable = raise_unavailable
        self.calls = 0

    def authorize(self) -> None:
        self.calls += 1
        if self.raise_unavailable:
            from picpay.domain.exceptions import AuthorizerUnavailable

            raise AuthorizerUnavailable()
        if not self.authorized:
            from picpay.domain.exceptions import TransferNotAuthorized

            raise TransferNotAuthorized()


class FakeNotifier:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list[tuple[int, str]] = []

    def notify(self, user_id: int, message: str) -> bool:
        self.calls.append((user_id, message))
        return self.ok


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def session(session_factory) -> Iterator[Session]:
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def fake_authorizer() -> Authorizer:
    return FakeAuthorizer()


@pytest.fixture
def fake_notifier() -> Notifier:
    return FakeNotifier()


@pytest.fixture
def client(
    session_factory,
    fake_authorizer,
    fake_notifier,
) -> Iterator[TestClient]:
    app = create_app()

    def _session_override() -> Iterator[Session]:
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[db_session] = _session_override
    app.dependency_overrides[authorizer_service] = lambda: fake_authorizer
    app.dependency_overrides[notifier_service] = lambda: fake_notifier

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _seed_user(
    session: Session,
    *,
    full_name: str,
    document: str,
    email: str,
    user_type: UserType,
    balance: Decimal,
) -> User:
    user = User(
        full_name=full_name,
        document=document,
        email=email,
        password_hash="x",
        user_type=user_type,
    )
    user.wallet = Wallet(balance=balance)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def seed_users(session: Session):
    def _make(
        payer_balance: Decimal = Decimal("100.00"),
        payee_balance: Decimal = Decimal("0.00"),
        payer_type: UserType = UserType.COMMON,
        payee_type: UserType = UserType.MERCHANT,
    ) -> tuple[User, User]:
        payer = _seed_user(
            session,
            full_name="Ana Pagadora",
            document="11111111111",
            email="ana@example.com",
            user_type=payer_type,
            balance=payer_balance,
        )
        payee = _seed_user(
            session,
            full_name="Loja Recebedora",
            document="22222222000122",
            email="loja@example.com",
            user_type=payee_type,
            balance=payee_balance,
        )
        return payer, payee

    return _make
