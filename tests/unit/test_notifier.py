from __future__ import annotations

import httpx

from picpay.config import Settings
from picpay.services.notifier import HttpNotifier


def _settings(max_attempts: int = 3) -> Settings:
    return Settings(
        notifier_url="https://example.test/notify",
        notifier_max_attempts=max_attempts,
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_envia_com_sucesso_em_2xx():
    chamadas = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(204)

    ok = HttpNotifier(_settings(), client=_client(handler)).notify(1, "ola")
    assert ok is True
    assert chamadas["n"] == 1


def test_retenta_em_5xx_e_persiste_falha():
    chamadas = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(503)

    ok = HttpNotifier(_settings(max_attempts=3), client=_client(handler)).notify(
        1, "ola"
    )
    assert ok is False
    assert chamadas["n"] == 3


def test_4xx_e_falha_sem_retry():
    chamadas = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(400)

    ok = HttpNotifier(_settings(max_attempts=3), client=_client(handler)).notify(
        1, "ola"
    )
    assert ok is False
    assert chamadas["n"] == 1


def test_retenta_em_erro_de_rede():
    chamadas = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        raise httpx.ConnectError("boom")

    ok = HttpNotifier(_settings(max_attempts=2), client=_client(handler)).notify(
        1, "ola"
    )
    assert ok is False
    assert chamadas["n"] == 2
