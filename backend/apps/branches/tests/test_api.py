import pytest

from apps.branches.models import Branch
from apps.core.testing import factories

pytestmark = pytest.mark.django_db

URL = "/api/branches/"


def detail_url(branch) -> str:
    return f"{URL}{branch.pk}/"


@pytest.fixture
def branches(branch, other_branch):
    return branch, other_branch


@pytest.fixture
def clients(client_for, admin_user, finance_user, manager, agent):
    return {
        "admin": client_for(admin_user),
        "finance": client_for(finance_user),
        "manager": client_for(manager),
        "agent": client_for(agent),
    }


@pytest.mark.parametrize(
    ("role", "visible"),
    [
        ("admin", {"BLR01", "MUM01"}),
        ("finance", {"BLR01", "MUM01"}),
        ("manager", {"BLR01"}),
        ("agent", {"BLR01"}),
    ],
)
def test_list_is_scoped_by_role(clients, branches, role, visible):
    res = clients[role].get(URL)

    assert res.status_code == 200
    assert {row["code"] for row in res.data["results"]} == visible


@pytest.mark.parametrize("role", ["manager", "agent"])
def test_other_branch_is_not_found_for_branch_roles(clients, branches, role):
    res = clients[role].get(detail_url(branches[1]))

    assert res.status_code == 404
    assert res.data["error"]["code"] == "NOT_FOUND"


def test_anonymous_cannot_list(api_client, branches):
    assert api_client.get(URL).status_code == 401


@pytest.mark.parametrize(
    ("role", "expected"), [("admin", 201), ("finance", 403), ("manager", 403), ("agent", 403)]
)
def test_only_admin_creates(clients, role, expected):
    res = clients[role].post(URL, {"code": "hyd01", "name": "Hyderabad", "city": "Hyderabad"})

    assert res.status_code == expected
    if expected == 201:
        assert res.data["code"] == "HYD01"
        assert res.data["agent_count"] == 0


def test_create_duplicate_code_conflicts(clients, branch):
    res = clients["admin"].post(URL, {"code": "BLR01", "name": "Again", "city": "Bengaluru"})

    assert res.status_code == 409
    assert res.data["error"]["code"] == "DUPLICATE_RECORD"


def test_create_validates_fields(clients):
    res = clients["admin"].post(URL, {"code": "B-1"})

    assert res.status_code == 400
    assert {"name", "city"} <= res.data["error"]["details"].keys()


@pytest.mark.parametrize(
    ("role", "expected"), [("admin", 200), ("finance", 403), ("manager", 403), ("agent", 403)]
)
def test_only_admin_updates(clients, branch, role, expected):
    res = clients[role].patch(detail_url(branch), {"name": "Renamed"}, format="json")

    assert res.status_code == expected


def test_code_cannot_be_changed_through_patch(clients, branch):
    res = clients["admin"].patch(detail_url(branch), {"code": "ZZZ99"}, format="json")

    assert res.status_code == 200
    assert res.data["code"] == "BLR01"


def test_deactivating_busy_branch_is_rejected(clients, customer):
    res = clients["admin"].patch(detail_url(customer.branch), {"is_active": False}, format="json")

    assert res.status_code == 422
    assert res.data["error"]["details"]["active_customers"] == 1


@pytest.mark.parametrize("method", ["put", "delete"])
def test_branches_cannot_be_replaced_or_deleted(clients, branch, method):
    res = getattr(clients["admin"], method)(detail_url(branch))

    assert res.status_code == 405


def test_list_includes_headcounts_and_filters(clients, customer, other_agent, other_branch):
    factories.AgentFactory(branch=customer.branch, is_active=False)
    other_branch.is_active = False
    other_branch.save()

    res = clients["admin"].get(URL, {"is_active": "true"})

    [row] = res.data["results"]
    assert row["code"] == "BLR01"
    assert row["agent_count"] == 2
    assert row["customer_count"] == 1


def test_search_by_city(clients, branches):
    res = clients["admin"].get(URL, {"search": "mumbai"})

    assert [row["code"] for row in res.data["results"]] == ["MUM01"]


def test_list_query_count_is_constant(clients, django_assert_max_num_queries):
    for n in range(10):
        factories.BranchFactory(code=f"QC{n:02d}")

    with django_assert_max_num_queries(5):
        res = clients["admin"].get(URL)

    assert res.data["count"] == Branch.objects.count()


@pytest.mark.parametrize("role", ["admin", "finance", "manager", "agent"])
def test_own_branch_is_readable_by_every_role(clients, branch, role):
    res = clients[role].get(detail_url(branch))

    assert res.status_code == 200
    assert res.data["code"] == "BLR01"


def test_update_rejects_unknown_branch(clients):
    res = clients["admin"].patch(f"{URL}999999/", {"name": "Ghost"}, format="json")

    assert res.status_code == 404
