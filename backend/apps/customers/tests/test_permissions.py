"""Role x endpoint matrix for customers, then row-level scoping per role."""

import pytest

pytestmark = pytest.mark.django_db

ROLES = ("admin", "finance", "manager", "agent")


def expect(admin: int, finance: int, manager: int, agent: int) -> dict[str, int]:
    return dict(zip(ROLES, (admin, finance, manager, agent), strict=True))


# endpoint -> (method, path, expected status per role). `{pk}` is the `own` customer.
MATRIX = {
    "list": ("get", "/api/customers/", expect(200, 200, 200, 200)),
    "retrieve": ("get", "/api/customers/{pk}/", expect(200, 200, 200, 200)),
    "loans": ("get", "/api/customers/{pk}/loans/", expect(200, 200, 200, 200)),
    "create": ("post", "/api/customers/", expect(201, 403, 201, 403)),
    "update": ("patch", "/api/customers/{pk}/", expect(200, 403, 200, 403)),
    "assign": ("post", "/api/customers/{pk}/assign/", expect(200, 403, 200, 403)),
    "replace": ("put", "/api/customers/{pk}/", expect(405, 403, 405, 403)),
    "delete": ("delete", "/api/customers/{pk}/", expect(405, 403, 405, 403)),
    "agent_route": ("get", "/api/agent/customers/", expect(403, 403, 403, 200)),
}


@pytest.fixture
def payloads(branch, other_agent):
    return {
        "create": {"full_name": "Lakshmi Rao", "phone": "9845011111", "branch": branch.pk},
        "update": {"full_name": "Lakshmi R."},
        "assign": {"agent_id": other_agent.pk},
    }


def call(client, method: str, path: str, data=None):
    return getattr(client, method)(path, data, format="json")


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("endpoint", MATRIX)
def test_role_matrix(clients, customers, payloads, endpoint, role):
    method, path, expected = MATRIX[endpoint]

    res = call(clients[role], method, path.format(pk=customers["own"].pk), payloads.get(endpoint))

    assert res.status_code == expected[role], res.data
    if res.status_code >= 400:
        assert res.data["error"]["code"]


@pytest.mark.parametrize("endpoint", MATRIX)
def test_anonymous_is_rejected(api_client, customer, endpoint):
    method, path, _ = MATRIX[endpoint]

    res = call(api_client, method, path.format(pk=customer.pk))

    assert res.status_code == 401
    assert res.data["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(
    ("role", "visible"),
    [
        ("admin", {"own", "colleague", "foreign"}),
        ("finance", {"own", "colleague", "foreign"}),
        ("manager", {"own", "colleague"}),
        ("agent", {"own"}),
    ],
)
def test_list_is_scoped(clients, customers, role, visible):
    res = clients[role].get("/api/customers/")

    ids = {row["id"] for row in res.data["results"]}
    assert ids == {customers[name].pk for name in visible}


@pytest.mark.parametrize(
    ("role", "target", "expected"),
    [
        ("admin", "foreign", 200),
        ("finance", "foreign", 200),
        ("manager", "colleague", 200),
        ("manager", "foreign", 404),
        ("agent", "colleague", 404),
        ("agent", "foreign", 404),
    ],
)
@pytest.mark.parametrize("suffix", ["", "loans/"])
def test_reads_outside_scope_are_not_found(clients, customers, role, target, expected, suffix):
    res = clients[role].get(f"/api/customers/{customers[target].pk}/{suffix}")

    assert res.status_code == expected
    if expected == 404:
        assert res.data["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    ("method", "suffix", "data"),
    [("patch", "", {"full_name": "Changed"}), ("post", "assign/", {"agent_id": None})],
)
def test_manager_cannot_write_to_another_branch(clients, customers, method, suffix, data):
    foreign = customers["foreign"]

    res = call(clients["manager"], method, f"/api/customers/{foreign.pk}/{suffix}", data)

    assert res.status_code == 404
    foreign.refresh_from_db()
    assert foreign.full_name != "Changed"
    assert foreign.assigned_agent_id is not None


def test_agent_route_lists_only_own_customers(clients, customers, client_for, other_agent):
    own = clients["agent"].get("/api/agent/customers/")
    colleague = client_for(other_agent).get("/api/agent/customers/")

    assert [row["id"] for row in own.data["results"]] == [customers["own"].pk]
    assert [row["id"] for row in colleague.data["results"]] == [customers["colleague"].pk]
