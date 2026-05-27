from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from picpay.domain.exceptions import DomainError

logger = logging.getLogger(__name__)


def _problem(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": code, "message": message},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return _problem(exc.status_code, exc.code, str(exc))

    @app.exception_handler(IntegrityError)
    async def _integrity_handler(_: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("violacao de integridade: %s", exc.orig)
        return _problem(
            status=409,
            code="conflict",
            message="recurso ja existe ou viola restricao de integridade",
        )
