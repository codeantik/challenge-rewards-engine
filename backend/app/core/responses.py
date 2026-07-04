"""The success side of the response envelope (see CLAUDE.md).

Every 2xx JSON body is `{"data": ..., "meta": ...}`. `meta` is omitted
(stays null) for endpoints that don't need pagination or similar extras.
"""

from typing import Any

from pydantic import BaseModel


class Envelope[T](BaseModel):
    data: T
    meta: dict[str, Any] | None = None
