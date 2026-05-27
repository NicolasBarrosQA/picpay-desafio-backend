from __future__ import annotations

import logging
from typing import Protocol

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from picpay.config import Settings

logger = logging.getLogger(__name__)


class NotificationFailed(Exception):
    pass


class NotificationRejected(Exception):
    pass


class Notifier(Protocol):
    def notify(self, user_id: int, message: str) -> bool:
        ...


class HttpNotifier:
    """Cliente para o servico de notificacao.

    O servico e instavel por design; a regra do desafio diz que a transferencia
    nao pode falhar por causa dele. Por isso aplicamos retry com backoff
    exponencial e tratamos falha definitiva como evento registravel, sem
    propagar excecao para a transferencia.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._url = settings.notifier_url
        self._timeout = settings.notifier_timeout
        self._max_attempts = max(1, settings.notifier_max_attempts)
        self._client = client

    def notify(self, user_id: int, message: str) -> bool:
        payload = {"user_id": user_id, "message": message}

        @retry(
            reraise=True,
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=0.2, min=0.2, max=2.0),
            retry=retry_if_exception_type(NotificationFailed),
        )
        def _do() -> None:
            try:
                response = self._post(payload)
            except httpx.HTTPError as exc:
                raise NotificationFailed(str(exc)) from exc

            if response.status_code >= 500 or response.status_code == 429:
                raise NotificationFailed(f"status={response.status_code}")
            if response.status_code >= 400:
                raise NotificationRejected(f"status={response.status_code}")

        try:
            _do()
        except NotificationRejected as exc:
            logger.warning(
                "notificacao recusada para usuario %s: %s",
                user_id,
                exc,
            )
            return False
        except (NotificationFailed, RetryError) as exc:
            logger.error(
                "falha ao notificar usuario %s apos %s tentativas: %s",
                user_id,
                self._max_attempts,
                exc,
            )
            return False
        return True

    def _post(self, payload: dict) -> httpx.Response:
        if self._client is not None:
            return self._client.post(self._url, json=payload, timeout=self._timeout)
        with httpx.Client(timeout=self._timeout) as client:
            return client.post(self._url, json=payload)
