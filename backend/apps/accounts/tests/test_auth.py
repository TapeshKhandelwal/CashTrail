import pytest
from rest_framework_simplejwt.tokens import AccessToken

from apps.core.testing.factories import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


def login(api_client, username, password=DEFAULT_PASSWORD):
    return api_client.post("/api/auth/login/", {"username": username, "password": password})


def test_login_returns_tokens_and_user(api_client, agent):
    res = login(api_client, agent.username)

    assert res.status_code == 200
    assert {"access", "refresh"} <= res.data.keys()
    assert res.data["user"]["role"] == "AGENT"
    assert res.data["user"]["branch_code"] == "BLR01"


def test_access_token_carries_role_and_branch_claims(api_client, manager):
    token = AccessToken(login(api_client, manager.username).data["access"])

    assert token["role"] == "BRANCH_MANAGER"
    assert token["branch_id"] == manager.branch_id
    assert token["branch_code"] == "BLR01"


def test_global_roles_have_no_branch_claim(api_client, finance_user):
    token = AccessToken(login(api_client, finance_user.username).data["access"])

    assert token["role"] == "FINANCE"
    assert token["branch_id"] is None


def test_wrong_password_uses_error_envelope(api_client, agent):
    res = login(api_client, agent.username, "wrong-password")

    assert res.status_code == 401
    assert res.data["error"]["code"] == "NO_ACTIVE_ACCOUNT"


def attempt(api_client, username, password="wrong", **headers):
    return api_client.post(
        "/api/auth/login/", {"username": username, "password": password}, **headers
    ).status_code


def test_login_is_throttled_per_address(api_client, agent):
    statuses = [attempt(api_client, f"nobody{n}") for n in range(11)]

    assert statuses[:10] == [401] * 10
    assert statuses[-1] == 429
    assert login(api_client, agent.username).data["error"]["code"] == "THROTTLED"


def test_spoofed_forwarded_for_does_not_reset_the_login_throttle(api_client):
    statuses = [
        attempt(api_client, f"nobody{n}", HTTP_X_FORWARDED_FOR=f"10.0.0.{n}") for n in range(11)
    ]

    assert statuses[-1] == 429


def from_web_app(address, secret="bff-secret"):
    return {"HTTP_X_CLIENT_IP": address, "HTTP_X_BFF_SECRET": secret}


def test_each_browser_behind_the_web_app_gets_its_own_bucket(api_client, settings):
    settings.BFF_SHARED_SECRET = "bff-secret"

    for n in range(10):
        attempt(api_client, f"nobody{n}", **from_web_app("198.51.100.1"))

    assert attempt(api_client, "nobody", **from_web_app("198.51.100.1")) == 429
    assert attempt(api_client, "nobody", **from_web_app("198.51.100.2")) == 401


@pytest.mark.parametrize(("configured", "sent"), [("", ""), ("bff-secret", "guess")])
def test_client_address_header_needs_the_shared_secret(api_client, settings, configured, sent):
    settings.BFF_SHARED_SECRET = configured

    statuses = [
        attempt(api_client, f"nobody{n}", **from_web_app(f"198.51.100.{n}", sent))
        for n in range(11)
    ]

    assert statuses[-1] == 429


def test_failed_logins_are_limited_per_username_across_addresses(api_client, agent, settings):
    settings.BFF_SHARED_SECRET = "bff-secret"

    statuses = [
        attempt(api_client, agent.username, **from_web_app(f"198.51.100.{n}")) for n in range(5)
    ]
    blocked = attempt(api_client, agent.username.upper(), **from_web_app("198.51.100.9"))
    right_password = attempt(
        api_client, agent.username, DEFAULT_PASSWORD, **from_web_app("198.51.100.10")
    )

    assert statuses == [401] * 5
    assert (blocked, right_password) == (429, 429)
    assert attempt(api_client, "someone-else", **from_web_app("198.51.100.11")) == 401


def test_successful_logins_do_not_count_toward_the_username_limit(api_client, agent):
    statuses = [attempt(api_client, agent.username, DEFAULT_PASSWORD) for _ in range(7)]

    assert statuses == [200] * 7


def test_me_requires_auth(api_client):
    res = api_client.get("/api/auth/me/")

    assert res.status_code == 401
    assert res.data["error"]["code"] == "NOT_AUTHENTICATED"


def test_me_returns_profile(agent_client, agent):
    res = agent_client.get("/api/auth/me/")

    assert res.status_code == 200
    assert res.data["username"] == agent.username
    assert res.data["branch_name"] == "Bengaluru Central"


def test_health_is_public(api_client):
    res = api_client.get("/api/health/")

    assert res.data["status"] == "ok"
    assert "X-Request-ID" in res.headers
