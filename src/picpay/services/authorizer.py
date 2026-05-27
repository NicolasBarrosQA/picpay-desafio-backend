from __future__ import annotations

import logging
from typing import Protocol

import httpx

from picpay.config import Settings
from picpay.domain.exceptions import AuthorizerUnavailable, TransferNotAuthorized

logger = logging.getLogger(__name__)


class Authorizer(Protocol):
    def authorize(self) -> None:
        ...


class HttpAuthorizer:
    """Cliente para o autorizador externo.

    O contrato do mock retorna 200 com `{"status":"success","data":{"authorization":true}}`
    quando autoriza e 403 caso contrario. Tratamos qualquer 4xx como negacao
    explicita e qualquer 5xx/timeout como indisponibilidade, propagando erros
    distintos para a camada superior decidir o status HTTP a devolver.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._url = settings.authorizer_url
        self._timeout = settings.authorizer_timeout
        self._client = client

    def authorize(self) -> None:
        try:
            response = self._request()
        except httpx.HTTPError as exc:
            logger.warning("autorizador indisponivel: %s", exc)
            raise AuthorizerUnavailable() from exc

        if response.status_code == 200:
            body = self._safe_json(response)
            authorized = bool(body.get("data", {}).get("authorization", False))
            if authorized:
                return
            raise TransferNotAuthorized()

        if 400 <= response.status_code < 500:
            raise TransferNotAuthorized()

        logger.warning(
            "autorizador respondeu status inesperado %s", response.status_code
        )
        raise AuthorizerUnavailable()

    def _request(self) -> httpx.Response:
        if self._client is not None:
            return self._client.get(self._url, timeout=self._timeout)
        with httpx.Client(timeout=self._timeout) as client:
            return client.get(self._url)

    @staticmethod
    def _safe_json(response: httpx.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
