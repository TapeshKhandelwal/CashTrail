"""Role x endpoint matrix for /api/collections/."""

import pytest

from apps.collections.models import Collection

pytestmark = pytest.mark.django_db

URL = "/api/collections/"
ROLES = ("admin_user", "finance_user", "manager", "agent")


@pytest.fixture
def receipt(agent, loan, collect) -> Collection:
    return collect(agent, loan, "100.00")


@pytest.fixture
def client_as(request, client_for):
    return lambda role: client_for(request.getfixturevalue(role))


def test_anonymous_is_rejected(api_client, receipt):
    for response in (
        api_client.get(URL),
        api_client.get(f"{URL}{receipt.pk}/"),
        api_client.get(f"{URL}daily-summary/"),
        api_client.post(URL, {}, format="json"),
    ):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(
    ("role", "status"),
    [("admin_user", 403), ("finance_user", 403), ("manager", 403), ("agent", 201)],
)
def test_only_agents_record_repayments(client_as, loan, idempotency_headers, role, status):
    response = client_as(role).post(
        URL, {"loan_id": loan.pk, "amount": "100.00"}, format="json", **idempotency_headers()
    )

    assert response.status_code == status


@pytest.mark.parametrize(
    ("role", "status"),
    [("admin_user", 403), ("finance_user", 403), ("manager", 403), ("agent", 200)],
)
def test_only_the_collecting_agent_voids(client_as, receipt, role, status):
    response = client_as(role).post(
        f"{URL}{receipt.pk}/void/", {"reason": "Mistake."}, format="json"
    )

    assert response.status_code == status


@pytest.mark.parametrize("role", ROLES)
def test_every_role_reads_within_scope(client_as, receipt, role):
    client = client_as(role)

    assert client.get(URL).status_code == 200
    assert client.get(f"{URL}{receipt.pk}/").status_code == 200
    assert client.get(f"{URL}daily-summary/").status_code == 200


@pytest.mark.parametrize("role", ("other_agent", "other_branch_manager", "other_branch_agent"))
def test_out_of_scope_users_get_not_found(client_as, receipt, role):
    client = client_as(role)

    assert client.get(f"{URL}{receipt.pk}/").status_code == 404
    assert receipt.pk not in {row["id"] for row in client.get(URL).json()["results"]}


def test_collections_have_no_edit_or_delete_endpoints(agent_client, receipt):
    for method in ("put", "patch", "delete"):
        response = getattr(agent_client, method)(f"{URL}{receipt.pk}/", {}, format="json")
        assert response.status_code == 405
