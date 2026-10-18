import hmac
import ipaddress
import uuid

from django.conf import settings

from .context import RequestContext, reset_request_context, set_request_context

REQUEST_ID_HEADER = "X-Request-ID"
# Set by the web app's server, which every browser request passes through, together with
# the shared secret that proves the header came from it rather than from a client.
CLIENT_IP_HEADER = "X-Client-IP"
BFF_SECRET_HEADER = "X-BFF-Secret"
USER_AGENT_MAX_LENGTH = 255


def _from_web_app(request) -> bool:
    secret = settings.BFF_SHARED_SECRET
    sent = request.headers.get(BFF_SECRET_HEADER, "")
    return bool(secret) and hmac.compare_digest(sent.encode(), secret.encode())


def _client_ip(request) -> str | None:
    """The browser's address as the web app saw it; otherwise the address our proxy saw: it
    appends the peer to X-Forwarded-For, so the right-most entry is trustworthy while
    anything to its left is whatever the client sent."""
    candidates = [request.META.get("REMOTE_ADDR", "")]
    if settings.TRUST_X_FORWARDED_FOR:
        candidates.insert(0, request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1])
    if _from_web_app(request):
        candidates.insert(0, request.headers.get(CLIENT_IP_HEADER, ""))
    for candidate in candidates:
        try:
            return str(ipaddress.ip_address(candidate.strip()))
        except ValueError:
            continue
    return None


def _request_id(request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    try:
        return str(uuid.UUID(incoming))
    except ValueError:
        return str(uuid.uuid4())


class RequestContextMiddleware:
    """Tags each request with an id (echoed back in `X-Request-ID`) for logs and the audit trail."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        context = RequestContext(
            request_id=_request_id(request),
            ip_address=_client_ip(request),
            user_agent=request.headers.get("User-Agent", "")[:USER_AGENT_MAX_LENGTH],
        )
        request.request_id = context.request_id
        token = set_request_context(context)
        try:
            response = self.get_response(request)
        finally:
            reset_request_context(token)
        response[REQUEST_ID_HEADER] = context.request_id
        return response
