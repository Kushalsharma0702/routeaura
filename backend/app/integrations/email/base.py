from __future__ import annotations

from typing import Protocol


class EmailError(Exception):
    pass


class EmailNotConfigured(EmailError):
    pass


class EmailProvider(Protocol):
    name: str

    def send(self, to: str, subject: str, body: str) -> None: ...
