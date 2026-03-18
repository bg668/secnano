from dataclasses import dataclass


@dataclass(frozen=True)
class RoleSpec:
    name: str
    soul: str
    role: str
    memory: str
    policy: str
