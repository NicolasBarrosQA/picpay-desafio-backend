from __future__ import annotations

from decimal import Decimal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from picpay.api.deps import db_session, user_repository
from picpay.domain.exceptions import UserNotFound
from picpay.domain.models import User, Wallet
from picpay.repositories.users import UserRepository
from picpay.schemas.users import UserCreate, UserResponse, WalletResponse

router = APIRouter(prefix="/users", tags=["users"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    session: Session = Depends(db_session),
    users: UserRepository = Depends(user_repository),
) -> User:
    if users.get_by_email(payload.email):
        raise HTTPException(status_code=409, detail="email ja cadastrado")
    if users.get_by_document(payload.document):
        raise HTTPException(status_code=409, detail="documento ja cadastrado")

    user = User(
        full_name=payload.full_name,
        document=payload.document,
        email=payload.email,
        password_hash=_hash_password(payload.password),
        user_type=payload.user_type,
    )
    user.wallet = Wallet(balance=Decimal(payload.initial_balance))
    users.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int, users: UserRepository = Depends(user_repository)
) -> User:
    user = users.get(user_id)
    if user is None:
        raise UserNotFound()
    return user


@router.get("/{user_id}/wallet", response_model=WalletResponse)
def get_wallet(
    user_id: int, users: UserRepository = Depends(user_repository)
) -> Wallet:
    user = users.get(user_id)
    if user is None or user.wallet is None:
        raise UserNotFound()
    return user.wallet
