from __future__ import annotations

import httpx
import pytest

from picpay.config import Settings
from picpay.domain.exceptions import AuthorizerUnavailable, TransferNotAuthorized
from picpay.services.authorizer import HttpAuthorizer


def _settings() -> Settings:
    return Settings(authorizer_url="https://example.test/authorize")


def _client(handler) -> httpx.Client:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def test_autoriza_quando_resposta_for_success_true():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "success", "data": {"authorization": True}}
        )

    HttpAuthorizer(_settings(), client=_client(handler)).authorize()


def test_nega_quando_resposta_for_success_false():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "fail", "data": {"authorization": False}}
        )

    with pytest.raises(TransferNotAuthorized):
        HttpAuthorizer(_settings(), client=_client(handler)).authorize()


def test_nega_em_403():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"status": "fail"})

    with pytest.raises(TransferNotAuthorized):
        HttpAuthorizer(_settings(), client=_client(handler)).authorize()


def test_indisponivel_em_5xx():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(AuthorizerUnavailable):
        HttpAuthorizer(_settings(), client=_client(handler)).authorize()


def test_indisponivel_em_erro_de_rede():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(AuthorizerUnavailable):
        HttpAuthorizer(_settings(), client=_client(handler)).authorize()
