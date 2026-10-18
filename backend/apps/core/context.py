"""Per-request context (request id, client IP, user agent) shared with audit logging.

Kept free of model imports so the logging config can load it before apps are ready.
"""

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str = ""


_EMPTY = RequestContext()
_current: ContextVar[RequestContext] = ContextVar("request_context")


def get_request_context() -> RequestContext:
    return _current.get(_EMPTY)


def set_request_context(context: RequestContext) -> Token:
    return _current.set(context)


def reset_request_context(token: Token) -> None:
    _current.reset(token)


class RequestContextLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_context().request_id or "-"
        return True
