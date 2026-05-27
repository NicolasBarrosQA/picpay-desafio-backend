from __future__ import annotations

from decimal import Decimal

import pytest

from picpay.domain.models import UserType

pytestmark = pytest.mark.integration


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_transfer_201(client, seed_users):
    payer, payee = seed_users(payer_balance=Decimal("250.00"))
    payload = {"value": 100.0, "payer": payer.id, "payee": payee.id}

    response = client.post("/transfer", json=payload)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["payer_id"] == payer.id
    assert body["payee_id"] == payee.id
    assert Decimal(body["amount"]) == Decimal("100.00")
    assert body["status"] == "completed"
    assert body["notification_status"] == "sent"


def test_lojista_nao_envia(client, seed_users):
    payer, payee = seed_users(payer_type=UserType.MERCHANT)
    response = client.post(
        "/transfer", json={"value": 10, "payer": payer.id, "payee": payee.id}
    )
    assert response.status_code == 403
    assert response.json()["error"] == "merchant_cannot_send"


def test_saldo_insuficiente_422(client, seed_users):
    payer, payee = seed_users(payer_balance=Decimal("1.00"))
    response = client.post(
        "/transfer", json={"value": 10, "payer": payer.id, "payee": payee.id}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "insufficient_funds"


def test_autorizador_negado_403(client, seed_users, fake_authorizer):
    fake_authorizer.authorized = False
    payer, payee = seed_users()
    response = client.post(
        "/transfer", json={"value": 10, "payer": payer.id, "payee": payee.id}
    )
    assert response.status_code == 403
    assert response.json()["error"] == "transfer_not_authorized"


def test_autorizador_indisponivel_503(client, seed_users, fake_authorizer):
    fake_authorizer.raise_unavailable = True
    payer, payee = seed_users()
    response = client.post(
        "/transfer", json={"value": 10, "payer": payer.id, "payee": payee.id}
    )
    assert response.status_code == 503


def test_payload_invalido_422(client, seed_users):
    payer, payee = seed_users()
    response = client.post(
        "/transfer", json={"value": -10, "payer": payer.id, "payee": payee.id}
    )
    assert response.status_code == 422

    response = client.post(
        "/transfer", json={"value": 1, "payer": payer.id, "payee": payer.id}
    )
    assert response.status_code in (400, 422)


def test_usuario_inexistente_404(client, seed_users):
    payer, _ = seed_users()
    response = client.post(
        "/transfer", json={"value": 1, "payer": payer.id, "payee": 9999}
    )
    assert response.status_code == 404


def test_criar_usuario_e_consultar_carteira(client):
    payload = {
        "full_name": "Beatriz Silva",
        "document": "987.654.321-00",
        "email": "bia@example.com",
        "password": "supersecret",
        "user_type": "common",
        "initial_balance": "50.00",
    }
    r = client.post("/users", json=payload)
    assert r.status_code == 201, r.text
    user_id = r.json()["id"]

    r = client.get(f"/users/{user_id}/wallet")
    assert r.status_code == 200
    assert Decimal(r.json()["balance"]) == Decimal("50.00")


def test_email_duplicado_409(client):
    payload = {
        "full_name": "Carlos",
        "document": "12345678901",
        "email": "carlos@example.com",
        "password": "senha123",
    }
    assert client.post("/users", json=payload).status_code == 201
    payload["document"] = "98765432100"
    assert client.post("/users", json=payload).status_code == 409
