from enum import Enum


class Status(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
