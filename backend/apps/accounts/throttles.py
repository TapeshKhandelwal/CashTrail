"""Rate limits keyed by the real client address, plus failed sign-ins per username."""

import hashlib

from rest_framework import throttling

from apps.core.context import get_request_context


class ClientAddressMixin:
    """Identify anonymous callers by the address the request middleware resolved, so every
    browser behind the web app gets its own bucket instead of sharing the app server's."""

    def get_ident(self, request):
        return get_request_context().ip_address or super().get_ident(request)


class UserRateThrottle(ClientAddressMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(ClientAddressMixin, throttling.ScopedRateThrottle):
    pass


class LoginUsernameThrottle(throttling.SimpleRateThrottle):
    """Failed sign-ins per username from any address, so guesses spread over many addresses
    still hit a limit. Only failures count (the view calls `record_failure`): signing in
    often never locks a user out."""

    scope = "login_username"

    def get_cache_key(self, request, view):
        data = request.data
        username = data.get("username") if hasattr(data, "get") else None
        if not isinstance(username, str) or not username.strip():
            return None
        ident = hashlib.sha256(username.strip().lower().encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view):
        self.key = self.get_cache_key(request, view) if self.rate else None
        if self.key is None:
            return True
        self.history = self.cache.get(self.key, [])
        self.now = self.timer()
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return True

    def record_failure(self):
        if getattr(self, "key", None) is None:
            return
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)
