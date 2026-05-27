from __future__ import annotations

import enum
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from picpay.db import Base

# BigInteger e o tipo correto para ids em producao (Postgres), mas o SQLite
# usado nos testes so faz autoincrement em INTEGER PRIMARY KEY. O variant
# mantem BigInteger para postgres/mysql e converte para Integer no sqlite.
PK = BigInteger().with_variant(Integer(), "sqlite")
FK = BigInteger().with_variant(Integer(), "sqlite")


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(
        py_enum,
        name=name,
        native_enum=False,
        length=20,
        values_callable=lambda enum_cls: [e.value for e in enum_cls],
    )


class UserType(enum.StrEnum):
    COMMON = "common"
    MERCHANT = "merchant"


class TransferStatus(enum.StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class NotificationStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    document: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_type: Mapped[UserType] = mapped_column(
        _enum(UserType, "user_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    wallet: Mapped[Wallet] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def is_merchant(self) -> bool:
        return self.user_type == UserType.MERCHANT

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email} type={self.user_type.value}>"


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        FK,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="wallet")

    def debit(self, amount: Decimal) -> None:
        from picpay.domain.exceptions import InsufficientFunds

        if amount > self.balance:
            raise InsufficientFunds(balance=self.balance, requested=amount)
        self.balance = self.balance - amount

    def credit(self, amount: Decimal) -> None:
        self.balance = self.balance + amount


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transfers_amount_positive"),
        CheckConstraint("payer_id <> payee_id", name="ck_transfers_distinct_parties"),
    )

    id: Mapped[int] = mapped_column(PK, primary_key=True, autoincrement=True)
    payer_id: Mapped[int] = mapped_column(
        FK, ForeignKey("users.id"), nullable=False, index=True
    )
    payee_id: Mapped[int] = mapped_column(
        FK, ForeignKey("users.id"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[TransferStatus] = mapped_column(
        _enum(TransferStatus, "transfer_status"),
        nullable=False,
        default=TransferStatus.PENDING,
    )
    notification_status: Mapped[NotificationStatus] = mapped_column(
        _enum(NotificationStatus, "notification_status"),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def mark_completed(self) -> None:
        self.status = TransferStatus.COMPLETED
        self.completed_at = datetime.now(UTC)

    def mark_failed(self, reason: str) -> None:
        self.status = TransferStatus.FAILED
        self.failure_reason = reason
