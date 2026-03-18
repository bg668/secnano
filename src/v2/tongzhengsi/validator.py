from .errors import ValidationError


def validate_role(role: str) -> str:
    value = role.strip()
    if not value:
        raise ValidationError("role is required")
    return value


def validate_task(task: str) -> str:
    value = task.strip()
    if not value:
        raise ValidationError("task is required")
    return value
