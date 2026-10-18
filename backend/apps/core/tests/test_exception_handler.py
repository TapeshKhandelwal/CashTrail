import json

import pytest
from django.core.exceptions import RequestDataTooBig
from django.db import connection
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory

from apps.core.exceptions import OverCollection
from apps.core.idempotency import require_idempotency_key
from apps.core.testing import factories
from apps.core.views import csrf_failure
from apps.deposits.models import BankDeposit

rf = APIRequestFactory()


def call(raiser, **headers):
    @api_view(["POST"])
    @permission_classes([AllowAny])
    def view(request):
        return raiser(request)

    return view(rf.post("/", {}, format="json", **headers))


def test_domain_error():
    def raiser(request):
        raise OverCollection(details={"outstanding": "1500.00"})

    res = call(raiser)

    assert res.status_code == 422
    assert res.data == {
        "error": {
            "code": "OVER_COLLECTION",
            "message": "The amount exceeds the outstanding balance.",
            "details": {"outstanding": "1500.00"},
        }
    }


def test_validation_error_keeps_field_details():
    class Input(serializers.Serializer):
        amount = serializers.DecimalField(max_digits=14, decimal_places=2)

    def raiser(request):
        Input(data={}).is_valid(raise_exception=True)

    res = call(raiser)

    assert res.status_code == 400
    assert res.data["error"]["code"] == "VALIDATION_ERROR"
    assert "amount" in res.data["error"]["details"]


def test_missing_idempotency_key():
    res = call(require_idempotency_key)

    assert res.status_code == 400
    assert res.data["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_valid_idempotency_key_passes():
    key = "9b2f8f4e-3c1d-4b8a-9f57-0d1e2a3b4c5d"

    def raiser(request):
        assert str(require_idempotency_key(request)) == key
        raise OverCollection

    assert call(raiser, HTTP_IDEMPOTENCY_KEY=key).status_code == 422


@pytest.mark.django_db
def test_named_constraint_maps_to_friendly_error():
    existing = factories.BankDepositFactory()

    def raiser(request):
        factories.BankDepositFactory(
            bank_account=existing.bank_account, reference_number=existing.reference_number.lower()
        )

    res = call(raiser)

    assert res.status_code == 409
    assert res.data["error"]["code"] == "DUPLICATE_BANK_REFERENCE"


@pytest.mark.django_db
def test_unnamed_check_violation_maps_to_422():
    def raiser(request):
        factories.CollectionFactory(amount=0)

    res = call(raiser)

    assert res.status_code == 422
    assert res.data["error"]["details"] == {"constraint": "collection_amount_positive"}


@pytest.mark.django_db
def test_trigger_exception_maps_to_record_locked():
    deposit = factories.BankDepositFactory(settled=True)

    def raiser(request):
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE deposits_bankdeposit SET settled_amount = 1 WHERE id = %s", [deposit.pk]
            )

    res = call(raiser)

    assert res.status_code == 409
    assert res.data["error"]["code"] == "RECORD_LOCKED"
    assert deposit.deposit_number in res.data["error"]["message"]


@pytest.mark.django_db
def test_protected_delete_maps_to_409(loan):
    def raiser(request):
        loan.customer.delete()

    res = call(raiser)

    assert res.status_code == 409
    assert res.data["error"]["code"] == "PROTECTED_RECORD"


@pytest.mark.django_db
def test_value_too_large_for_its_column_is_422():
    def raiser(request):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1e20::numeric(14, 2)")

    res = call(raiser)

    assert res.status_code == 422
    assert res.data["error"]["code"] == "VALIDATION_FAILED"


def test_suspicious_request_is_a_400(caplog):
    def raiser(request):
        raise RequestDataTooBig("Request body exceeded DATA_UPLOAD_MAX_MEMORY_SIZE.")

    res = call(raiser)

    assert res.status_code == 400
    assert res.data["error"]["code"] == "BAD_REQUEST"
    assert "Unhandled error" not in caplog.text


@pytest.mark.usefixtures("branch")
def test_out_of_range_date_in_a_query_is_422(admin_client):
    for url in (
        "/api/collections/?date=9999-12-31",
        "/api/dashboard/summary/?date_from=9999-12-01&date_to=9999-12-31",
        "/api/audit-logs/?date_to=9999-12-31",
        "/api/reconciliation/branch-summary/?date_from=9999-12-01&date_to=9999-12-31",
        "/api/gateway-settlements/pending/?up_to_date=9999-12-31",
    ):
        res = admin_client.get(url)

        assert res.status_code == 422, url
        assert res.json()["error"]["message"] == "Date is out of range."


def test_unexpected_error_is_generic_500(caplog):
    def raiser(request):
        raise KeyError("secret detail")

    res = call(raiser)

    assert res.status_code == 500
    assert res.data["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in res.data["error"]["message"]
    assert "Unhandled error" in caplog.text


@pytest.mark.django_db
def test_unknown_url_returns_json_404(api_client, settings):
    settings.DEBUG = False

    res = api_client.get("/api/does-not-exist/")

    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_disallowed_host_returns_json_400(api_client, settings):
    settings.DEBUG = False

    res = api_client.get("/api/health/", HTTP_HOST="evil.example")

    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BAD_REQUEST"


def test_csrf_failure_returns_json_403(rf):
    res = csrf_failure(rf.post("/"), reason="CSRF cookie not set.")

    assert res.status_code == 403
    assert json.loads(res.content)["error"]["code"] == "CSRF_FAILED"


@pytest.mark.django_db
def test_oversized_webhook_body_is_a_400(api_client, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 1024

    res = api_client.post(
        "/api/payments/webhooks/razorpay/", b"x" * 2048, content_type="application/json"
    )

    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BAD_REQUEST"


@pytest.mark.django_db
def test_request_id_is_echoed(api_client):
    request_id = "0f0e0d0c-0b0a-4908-8706-050403020100"

    res = api_client.get("/api/health/", HTTP_X_REQUEST_ID=request_id)

    assert res.headers["X-Request-ID"] == request_id


@pytest.mark.django_db
def test_deposit_reference_is_normalized():
    deposit = factories.BankDepositFactory(reference_number="  slip 00a1 ")

    assert BankDeposit.objects.get(pk=deposit.pk).reference_number == "SLIP00A1"
