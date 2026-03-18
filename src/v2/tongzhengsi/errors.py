class IngressError(Exception):
    code = "ingress_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class ValidationError(IngressError):
    code = "validation_error"
