from decimal import Decimal


class DomainError(Exception):
    """Erros previsiveis do dominio. Mapeados pela camada HTTP em respostas 4xx."""

    code: str = "domain_error"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__doc__ or self.code)


class UserNotFound(DomainError):
    """Usuario nao encontrado."""

    code = "user_not_found"
    status_code = 404


class MerchantCannotSend(DomainError):
    """Lojistas nao podem enviar transferencias, apenas receber."""

    code = "merchant_cannot_send"
    status_code = 403


class SameUserTransfer(DomainError):
    """Pagador e recebedor nao podem ser o mesmo usuario."""

    code = "same_user_transfer"


class InsufficientFunds(DomainError):
    """Saldo insuficiente para concluir a transferencia."""

    code = "insufficient_funds"
    status_code = 422

    def __init__(self, balance: Decimal, requested: Decimal) -> None:
        super().__init__(
            f"saldo insuficiente: disponivel={balance}, solicitado={requested}"
        )
        self.balance = balance
        self.requested = requested


class InvalidTransferAmount(DomainError):
    """O valor da transferencia precisa ser maior que zero."""

    code = "invalid_amount"


class TransferNotAuthorized(DomainError):
    """Transferencia negada pelo servico autorizador externo."""

    code = "transfer_not_authorized"
    status_code = 403


class AuthorizerUnavailable(DomainError):
    """Servico autorizador indisponivel no momento."""

    code = "authorizer_unavailable"
    status_code = 503
