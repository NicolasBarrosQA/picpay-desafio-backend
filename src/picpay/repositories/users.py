from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from picpay.domain.models import User, Wallet


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(joinedload(User.wallet))
            .where(User.id == user_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_document(self, document: str) -> User | None:
        stmt = select(User).where(User.document == document)
        return self.session.execute(stmt).scalar_one_or_none()

    def lock_wallets(self, payer_id: int, payee_id: int) -> tuple[Wallet, Wallet]:
        """Carrega ambas carteiras com SELECT ... FOR UPDATE.

        Os ids sao ordenados antes do lock para evitar deadlocks quando duas
        transferencias entre os mesmos usuarios ocorrem em sentidos opostos.
        """
        ordered = sorted({payer_id, payee_id})
        stmt = (
            select(Wallet)
            .where(Wallet.user_id.in_(ordered))
            .with_for_update()
            .order_by(Wallet.user_id)
        )
        wallets = self.session.execute(stmt).scalars().all()
        by_user = {w.user_id: w for w in wallets}
        payer_wallet = by_user.get(payer_id)
        payee_wallet = by_user.get(payee_id)
        if payer_wallet is None or payee_wallet is None:
            raise LookupError("carteira nao encontrada para um dos usuarios")
        return payer_wallet, payee_wallet

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user
