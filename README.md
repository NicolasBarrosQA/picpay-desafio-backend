# Desafio Backend PicPay

[![CI](https://github.com/NicolasBarrosQA/picpay-desafio-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/NicolasBarrosQA/picpay-desafio-backend/actions/workflows/ci.yml)

API REST de transferências financeiras entre usuários, atendendo ao
[desafio backend do PicPay](https://github.com/PicPay/picpay-desafio-backend).

Stack: **Python 3.12 · FastAPI · SQLAlchemy 2.0 · PostgreSQL 16 · Alembic ·
Pytest · Docker**.

---

## Sumário

- [Como rodar](#como-rodar)
- [Endpoint principal](#endpoint-principal)
- [Endpoints auxiliares](#endpoints-auxiliares)
- [Regras de negócio cobertas](#regras-de-negócio-cobertas)
- [Decisões de arquitetura](#decisões-de-arquitetura)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Qualidade e CI](#qualidade-e-ci)
- [Histórico de versionamento](#histórico-de-versionamento)
- [Evoluções possíveis](#evoluções-possíveis)

---

## Como rodar

### Com Docker (recomendado)

```bash
cp .env.example .env
docker compose up --build
```

A API sobe em `http://localhost:8000`. As migrations rodam automaticamente
antes do `uvicorn` (`alembic upgrade head`).

Documentação interativa: `http://localhost:8000/docs`.

### Localmente, sem Docker

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS

pip install -e ".[dev]"

# subir um Postgres em 5432 ou ajustar DATABASE_URL no .env
alembic upgrade head
uvicorn picpay.main:app --reload
```

---

## Endpoint principal

### `POST /transfer`

Realiza uma transferência entre dois usuários.

**Request**

```http
POST /transfer
Content-Type: application/json

{
  "value": 100.00,
  "payer": 4,
  "payee": 15
}
```

**Response 201 — sucesso**

```json
{
  "id": 1,
  "payer_id": 4,
  "payee_id": 15,
  "amount": "100.00",
  "status": "completed",
  "notification_status": "sent",
  "created_at": "2026-05-20T20:30:00Z",
  "completed_at": "2026-05-20T20:30:00Z"
}
```

**Erros mapeados**

| HTTP | `error`                    | Significado                                            |
| ---- | -------------------------- | ------------------------------------------------------ |
| 400  | `same_user_transfer`       | Pagador igual ao recebedor.                            |
| 400  | `invalid_amount`           | Valor menor ou igual a zero.                           |
| 403  | `merchant_cannot_send`     | Lojista tentando enviar — só pode receber.             |
| 403  | `transfer_not_authorized`  | Autorizador externo negou.                             |
| 404  | `user_not_found`           | Pagador ou recebedor não existem.                      |
| 422  | `insufficient_funds`       | Saldo insuficiente.                                    |
| 422  | (validação Pydantic)       | Payload mal-formado.                                   |
| 503  | `authorizer_unavailable`   | Autorizador fora do ar/timeout — transferência abortada. |

---

## Endpoints auxiliares

Embora o desafio não exija cadastro nem autenticação, a API oferece endpoints
auxiliares para facilitar testes manuais e validações sem carga manual no banco:

- `POST /users` — cria usuário (`common` ou `merchant`) e carteira já com saldo
  inicial. Documento aceita CPF ou CNPJ com ou sem formatação.
- `GET /users/{id}` — consulta usuário.
- `GET /users/{id}/wallet` — consulta saldo.
- `GET /health` — healthcheck para orquestradores.

Senha é armazenada com `bcrypt`. Email e documento têm constraint de unicidade
no banco.

---

## Regras de negócio cobertas

Conforme o enunciado oficial:

- [x] Dois tipos de usuário: **comum** e **lojista**.
- [x] Lojistas **apenas recebem** transferências.
- [x] CPF/CNPJ e e-mail únicos no sistema.
- [x] Validação de saldo antes de transferir.
- [x] Transação **atômica**: débito e crédito num único `BEGIN/COMMIT`,
      com `SELECT ... FOR UPDATE` ordenado por id para evitar deadlock.
      Qualquer falha durante o débito/crédito faz rollback completo.
- [x] Consulta ao **autorizador externo** antes de efetivar
      (`GET https://util.devi.tools/api/v2/authorize`).
- [x] **Notificação** ao recebedor após o sucesso
      (`POST https://util.devi.tools/api/v1/notify`), com retry exponencial
      e tolerância a indisponibilidade — falha de notificação **não reverte** a
      transferência (registrada como `notification_status=failed`).
- [x] RESTful.

---

## Decisões de arquitetura

### Camadas

```
api/           HTTP: rotas, schemas Pydantic, error handlers, dependências.
services/      Regras de negócio e orquestração (TransferService, Authorizer, Notifier).
repositories/  Acesso a dados sobre SQLAlchemy Session.
domain/        Modelos ORM com comportamento (debit/credit), enums e exceções.
schemas/       Contratos de entrada e saída (Pydantic v2).
```

A separação é enxuta e adequada ao escopo do desafio. O domínio concentra as
regras essenciais nos modelos SQLAlchemy, como `debit`/`credit` no agregado
`Wallet`, enquanto os serviços coordenam transação, autorização externa e
notificação. Os repositórios isolam consultas específicas, incluindo o lock das
carteiras, e tornam os testes mais diretos.

### Concorrência e consistência

- **`Decimal(14,2)`** no schema para qualquer valor monetário. Nenhum `float`
  no caminho do dinheiro. Pydantic recebe número JSON e converte; o serviço
  re-quantiza com `ROUND_HALF_UP`.
- **`SELECT ... FOR UPDATE`** em ambas carteiras, **ordenadas por `user_id`**.
  Duas transferências cruzadas entre os mesmos dois usuários (A→B e B→A)
  pegam os locks na mesma ordem e não fazem deadlock.
- **Constraint `balance >= 0`** no banco (`CHECK`). Defesa em profundidade:
  mesmo que o código falhe, o banco recusa saldo negativo.
- **Constraint `payer_id <> payee_id`** e **`amount > 0`** no banco.

### Chamadas externas

- **Autorizador**: chamado **antes** de qualquer mutação. Locks no banco
  são pegos **depois** do autorizador responder, para não segurar conexão
  durante a chamada HTTP. Status `2xx` com `data.authorization=true` autoriza;
  qualquer `4xx` é negação; `5xx`/timeout vira `503` para o cliente.
- **Notificador**: chamado **após** o commit da transferência. Usa retry
  exponencial (`tenacity`, 3 tentativas por padrão) para respostas `5xx`,
  `429` e falhas de rede. Rejeições `4xx` são tratadas como falha definitiva,
  registradas em `notification_status=failed`, sem reverter a transferência.

### Por que FastAPI

Stack moderna, suporte nativo a Pydantic v2, OpenAPI gratuito,
sistema de DI por `Depends` que combina bem com testes
(via `app.dependency_overrides`). Performance equivalente ou superior aos
frameworks tradicionais para esse perfil de carga.

### Trade-offs assumidos

- **SQLite nos testes**: `with_for_update()` é silenciosamente ignorado pelo
  SQLite, mas o caminho de código é o mesmo. Em produção (Postgres) os locks
  são efetivos. Testes ficam rápidos e sem dependência externa.
- **Sem auth**: o enunciado diz explicitamente que cadastro e autenticação
  não são avaliados. Manter o foco no que importa.
- **Sem outbox dedicada**: a notificação tem retry síncrono. Para SLA mais
  rigorosa, a evolução natural é persistir eventos de notificação e
  processá-los por worker.

---

## Estrutura do projeto

```
.
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .github/workflows/ci.yml
├── migrations/
│   └── versions/0001_initial.py
├── src/picpay/
│   ├── main.py                # bootstrap do FastAPI
│   ├── config.py              # settings via pydantic-settings
│   ├── db.py                  # engine + SessionLocal + Base
│   ├── api/
│   │   ├── deps.py            # injeção de dependências
│   │   ├── errors.py          # exception handlers
│   │   ├── transfers.py       # POST /transfer
│   │   ├── users.py           # CRUD mínimo + wallet
│   │   └── health.py
│   ├── domain/
│   │   ├── models.py          # User, Wallet, Transfer + enums
│   │   └── exceptions.py      # erros de domínio mapeados a HTTP
│   ├── repositories/
│   │   ├── users.py           # lock_wallets() com FOR UPDATE
│   │   └── transfers.py
│   ├── services/
│   │   ├── transfers.py       # orquestra a transferência
│   │   ├── authorizer.py      # cliente HTTP do autorizador externo
│   │   └── notifier.py        # cliente HTTP com retry exponencial
│   └── schemas/
│       ├── transfers.py
│       └── users.py
└── tests/
    ├── conftest.py            # fixtures: engine SQLite, client, fakes
    ├── unit/
    │   ├── test_transfer_service.py
    │   ├── test_authorizer.py
    │   ├── test_database_constraints.py
    │   └── test_notifier.py
    └── integration/
        └── test_transfer_api.py
```

---

## Testes

```bash
pytest --cov --cov-report=term-missing
```

- **32 testes**, **93% de cobertura** no último run.
- Unitários para o `TransferService` (regras de negócio: lojista não envia,
  saldo insuficiente, autorizador negando/indisponível, falha de notificação
  não reverte, valor inválido, payer == payee, arredondamento).
- Unitários para `HttpAuthorizer` e `HttpNotifier` usando `httpx.MockTransport`.
- Integração da rota `POST /transfer` ponta-a-ponta via `TestClient` com
  SQLite em memória e fakes injetadas via `app.dependency_overrides`.

---

## Qualidade e CI

O repositório inclui workflow de CI no GitHub Actions com:

- `ruff check .`
- `pytest --cov --cov-report=term-missing`
- `pip-audit`
- `docker build`

Essas verificações cobrem estilo, regressões de domínio/API, vulnerabilidades
conhecidas nas dependências instaladas e validade básica da imagem Docker.

---

## Histórico de versionamento

O repositório foi publicado com um commit único por se tratar de uma entrega
técnica fechada, desenvolvida e validada localmente antes da publicação. Esse
formato mantém o histórico remoto objetivo: um snapshot completo e reproduzível
do desafio, contendo implementação, testes, migrations, Docker e documentação no
mesmo estado validado.

Em um projeto colaborativo ou evolutivo, o fluxo natural seria trabalhar com
commits menores por feature, correção e refatoração. Para este desafio, o commit
único evita expor ruído de experimentação local e deixa a avaliação concentrada
no resultado final executável.

---

## Evoluções possíveis

Itens adequados para um backlog de produção:

- **Outbox pattern** para notificações — persistir e processar via worker.
- **Idempotency-Key** no `POST /transfer` para retries de cliente.
- **Observabilidade**: tracing OTel, métricas Prometheus, logs estruturados
  (JSON com `correlation_id`).
- **Rate limiting** por usuário no endpoint de transferência.
- **Autenticação** OAuth2/JWT em cima do `POST /users` e do `/transfer`.
