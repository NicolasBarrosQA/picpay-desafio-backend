from __future__ import annotations

import logging

from fastapi import FastAPI

from picpay.api.errors import register_exception_handlers
from picpay.api.health import router as health_router
from picpay.api.transfers import router as transfers_router
from picpay.api.users import router as users_router
from picpay.config import get_settings


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    _configure_logging(settings.log_level)

    app = FastAPI(
        title="PicPay - Desafio Backend",
        description=(
            "API de transferencias entre usuarios. Implementa o desafio backend "
            "do PicPay: validacoes de regra de negocio, autorizador externo, "
            "transacao atômica e notificacao com retry."
        ),
        version="0.1.0",
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(users_router)
    app.include_router(transfers_router)
    return app


app = create_app()
