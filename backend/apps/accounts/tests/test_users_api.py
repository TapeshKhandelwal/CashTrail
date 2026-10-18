import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditLog
from apps.core.testing import factories

pytestmark = pytest.mark.django_db

URL = "/api/users/"
STRONG_PASSWORD = "Ledger-Stone-42"


def detail_url(user, action: str = "") -> str:
    return f"{URL}{user.pk}/{action + '/' if action else ''}"


@pytest.fixture
def clients(client_for, admin_user, finance_user, manager, agent):
    return {
        "admin": client_for(admin_user),
        "finance": client_for(finance_user),
        "manager": client_for(manager),
        "agent": client_for(agent),
    }


@pytest.fixture
def new_agent_payload(branch):
    return {
        "username": "field.agent",
        "password": STRONG_PASSWORD,
        "first_name": "Meena",
        "last_name": "Iyer",
        "phone": "+91 98450 12345",
        "role": "AGENT",
        "branch": branch.pk,
    }


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 200), ("finance", 200), ("manager", 200), ("agent", 403)],
)
def test_list_permissions(clients, role, expected):
    assert clients[role].get(URL).status_code == expected


def test_anonymous_is_rejected(api_client):
    assert api_client.get(URL).status_code == 401


def test_manager_sees_only_agents_of_own_branch(
    clients, agent, other_agent, other_branch_agent, other_branch_manager
):
    res = clients["manager"].get(URL)

    assert {row["username"] for row in res.data["results"]} == {
        agent.username,
        other_agent.username,
    }


@pytest.mark.parametrize("target", ["other_branch_agent", "finance_user", "manager"])
def test_manager_cannot_read_users_outside_their_agents(clients, request, target):
    res = clients["manager"].get(detail_url(request.getfixturevalue(target)))

    assert res.status_code == 404


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 201), ("finance", 403), ("manager", 403), ("agent", 403)],
)
def test_only_admin_creates_users(clients, new_agent_payload, role, expected):
    res = clients[role].post(URL, new_agent_payload, format="json")

    assert res.status_code == expected


def test_create_returns_profile_without_password(clients, new_agent_payload, api_client):
    res = clients["admin"].post(URL, new_agent_payload, format="json")

    assert res.data["phone"] == "+919845012345"
    assert res.data["branch_code"] == "BLR01"
    assert res.data["is_active"] is True
    assert "password" not in res.data
    login = api_client.post(
        "/api/auth/login/", {"username": "field.agent", "password": STRONG_PASSWORD}
    )
    assert login.status_code == 200


def test_create_agent_without_branch_is_rejected(clients, new_agent_payload):
    res = clients["admin"].post(URL, new_agent_payload | {"branch": None}, format="json")

    assert res.status_code == 422
    assert res.data["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"role": "SUPERHERO"}, "role"),
        ({"branch": 999999}, "branch"),
        ({"phone": "12ab"}, "phone"),
        ({"username": "has space"}, "username"),
    ],
)
def test_create_validates_input(clients, new_agent_payload, override, field):
    res = clients["admin"].post(URL, new_agent_payload | override, format="json")

    assert res.status_code == 400
    assert field in res.data["error"]["details"]


def test_weak_password_is_rejected(clients, new_agent_payload):
    res = clients["admin"].post(URL, new_agent_payload | {"password": "password"}, format="json")

    assert res.status_code == 422
    assert "password" in res.data["error"]["details"]


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 200), ("finance", 403), ("manager", 403), ("agent", 403)],
)
def test_only_admin_updates_users(clients, other_agent, role, expected):
    res = clients[role].patch(detail_url(other_agent), {"first_name": "Kiran"}, format="json")

    assert res.status_code == expected


def test_update_ignores_read_only_fields(clients, other_agent):
    res = clients["admin"].patch(
        detail_url(other_agent), {"username": "hijack", "is_active": False}, format="json"
    )

    assert res.status_code == 200
    assert (res.data["username"], res.data["is_active"]) == ("agent2", True)


@pytest.mark.parametrize("action", ["deactivate", "activate"])
@pytest.mark.parametrize("role", ["finance", "manager", "agent"])
def test_only_admin_changes_activation(clients, other_agent, role, action):
    assert clients[role].post(detail_url(other_agent, action)).status_code == 403


def test_deactivated_user_loses_access_immediately(clients, client_for, manager):
    manager_client = client_for(manager)
    refresh = RefreshToken.for_user(manager)

    res = clients["admin"].post(detail_url(manager, "deactivate"))

    assert res.status_code == 200
    assert res.data["is_active"] is False
    assert manager_client.get("/api/auth/me/").status_code == 401
    refreshed = manager_client.post("/api/auth/refresh/", {"refresh": str(refresh)})
    assert refreshed.status_code == 401


def test_role_change_ends_the_users_refresh_session(clients, client_for, manager):
    refresh = RefreshToken.for_user(manager)

    res = clients["admin"].patch(detail_url(manager), {"role": "FINANCE"}, format="json")

    assert res.status_code == 200
    refreshed = client_for(manager).post("/api/auth/refresh/", {"refresh": str(refresh)})
    assert refreshed.status_code == 401


def test_web_app_client_address_is_audited(clients, settings, manager):
    settings.BFF_SHARED_SECRET = "bff-secret"

    clients["admin"].post(
        detail_url(manager, "deactivate"),
        HTTP_X_CLIENT_IP="198.51.100.30",
        HTTP_X_BFF_SECRET="bff-secret",
    )

    assert AuditLog.objects.get(action=AuditAction.USER_UPDATED).ip_address == "198.51.100.30"


def test_agent_with_customers_cannot_be_deactivated(clients, customer):
    res = clients["admin"].post(detail_url(customer.assigned_agent, "deactivate"))

    assert res.status_code == 422
    assert res.data["error"]["details"]["assigned_customers"] == 1


def test_activate_restores_access(clients, client_for, other_agent):
    clients["admin"].post(detail_url(other_agent, "deactivate"))

    res = clients["admin"].post(detail_url(other_agent, "activate"))

    assert res.data["is_active"] is True
    assert client_for(other_agent).get("/api/auth/me/").status_code == 200


def test_set_password(clients, api_client, other_agent):
    res = clients["admin"].post(
        detail_url(other_agent, "set-password"), {"password": STRONG_PASSWORD}, format="json"
    )

    assert res.status_code == 204
    login = api_client.post(
        "/api/auth/login/", {"username": other_agent.username, "password": STRONG_PASSWORD}
    )
    assert login.status_code == 200


@pytest.mark.parametrize("role", ["finance", "manager", "agent"])
def test_only_admin_sets_passwords(clients, other_agent, role):
    res = clients[role].post(
        detail_url(other_agent, "set-password"), {"password": STRONG_PASSWORD}, format="json"
    )

    assert res.status_code == 403


def test_filters_and_search(clients, agent, other_agent, other_branch_agent):
    other_agent.is_active = False
    other_agent.save()

    by_branch = clients["admin"].get(
        URL, {"role": "AGENT", "branch": agent.branch_id, "is_active": "true"}
    )
    by_search = clients["admin"].get(URL, {"search": "agent_mum"})

    assert [row["username"] for row in by_branch.data["results"]] == [agent.username]
    assert [row["username"] for row in by_search.data["results"]] == ["agent_mum"]


def test_list_query_count_is_constant(clients, branch, django_assert_max_num_queries):
    factories.AgentFactory.create_batch(15, branch=branch)

    with django_assert_max_num_queries(5):
        res = clients["admin"].get(URL)

    assert res.data["count"] == User.objects.count()


@pytest.mark.parametrize(
    ("role", "expected"),
    [("admin", 200), ("finance", 200), ("manager", 200), ("agent", 403)],
)
def test_retrieve_own_branch_agent(clients, other_agent, role, expected):
    res = clients[role].get(detail_url(other_agent))

    assert res.status_code == expected
    if expected == 403:
        assert res.data["error"]["code"] == "PERMISSION_DENIED"


def test_manager_filtering_another_branch_gets_nothing(clients, other_branch_agent):
    res = clients["manager"].get(URL, {"branch": other_branch_agent.branch_id})

    assert res.data["count"] == 0


@pytest.mark.parametrize("method", ["put", "delete"])
def test_users_cannot_be_replaced_or_deleted(clients, other_agent, method):
    assert getattr(clients["admin"], method)(detail_url(other_agent)).status_code == 405


def test_moving_agent_to_global_role_clears_branch(clients, other_agent):
    res = clients["admin"].patch(detail_url(other_agent), {"role": "FINANCE"}, format="json")

    assert res.status_code == 200
    assert (res.data["role"], res.data["branch"]) == ("FINANCE", None)


def test_moving_user_to_inactive_branch_is_rejected(clients, other_agent):
    closed = factories.BranchFactory(code="OLD01", is_active=False)

    res = clients["admin"].patch(detail_url(other_agent), {"branch": closed.pk}, format="json")

    assert res.status_code == 422
    assert res.data["error"]["code"] == "VALIDATION_FAILED"


def test_promoting_finance_to_manager_requires_branch(clients, finance_user, branch):
    missing = clients["admin"].patch(
        detail_url(finance_user), {"role": "BRANCH_MANAGER"}, format="json"
    )
    with_branch = clients["admin"].patch(
        detail_url(finance_user), {"role": "BRANCH_MANAGER", "branch": branch.pk}, format="json"
    )

    assert missing.status_code == 422
    assert "branch" in missing.data["error"]["details"]
    assert (with_branch.status_code, with_branch.data["branch_code"]) == (200, "BLR01")


def test_admin_cannot_deactivate_self(clients, admin_user):
    res = clients["admin"].post(detail_url(admin_user, "deactivate"))

    assert res.status_code == 422


def test_set_password_rejects_weak_password(clients, other_agent):
    res = clients["admin"].post(
        detail_url(other_agent, "set-password"), {"password": "password"}, format="json"
    )

    assert res.status_code == 422
    assert "password" in res.data["error"]["details"]


def test_unknown_user_is_not_found(clients):
    res = clients["admin"].get(f"{URL}999999/")

    assert res.status_code == 404
    assert res.data["error"]["code"] == "NOT_FOUND"
