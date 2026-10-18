import importlib

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import clear_url_caches

import config.urls
from apps.accounts.models import User
from apps.branches.models import Branch
from apps.core.middleware import _client_ip
from apps.customers.models import Customer
from apps.deposits.models import BankAccount


@pytest.fixture
def reload_urls(settings):
    """Rebuild the URLconf under the current settings, and restore it afterwards."""

    original = settings.ADMIN_ENABLED, settings.ADMIN_URL

    def reload():
        clear_url_caches()
        return importlib.reload(config.urls)

    yield reload
    settings.ADMIN_ENABLED, settings.ADMIN_URL = original
    reload()


class TestAdminSite:
    def test_admin_is_not_served_unless_enabled(self, client, settings, reload_urls):
        settings.ADMIN_ENABLED = False
        reload_urls()

        assert client.get("/admin/login/").status_code == 404

    @pytest.mark.django_db
    def test_admin_login_is_throttled(self, client, settings, reload_urls):
        settings.ADMIN_ENABLED = True
        settings.ADMIN_URL = "ops-console/"
        settings.STORAGES = {
            **settings.STORAGES,
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
        reload_urls()

        statuses = [
            client.post("/ops-console/login/", {"username": "admin", "password": "x"}).status_code
            for _ in range(11)
        ]

        assert statuses[0] == 200
        assert statuses[-1] == 429
        assert client.get("/admin/login/").status_code == 404

    @pytest.mark.parametrize("model", [Branch, Customer, BankAccount, User])
    def test_master_data_is_read_only_in_the_admin(self, rf, model):
        model_admin = admin.site._registry[model]
        request = rf.get("/")

        assert not model_admin.has_add_permission(request)
        assert not model_admin.has_change_permission(request)
        assert not model_admin.has_delete_permission(request)


class TestClientAddress:
    @pytest.fixture
    def request_with(self):
        def make(forwarded: str | None = None, remote: str = "203.0.113.5", **extra):
            headers = {"REMOTE_ADDR": remote, **extra}
            if forwarded is not None:
                headers["HTTP_X_FORWARDED_FOR"] = forwarded
            return RequestFactory().get("/", **headers)

        return make

    def test_takes_the_hop_the_proxy_appended(self, settings, request_with):
        settings.TRUST_X_FORWARDED_FOR = True

        assert _client_ip(request_with("6.6.6.6, 198.51.100.7")) == "198.51.100.7"

    def test_ignores_a_value_that_is_not_an_address(self, settings, request_with):
        settings.TRUST_X_FORWARDED_FOR = True

        assert _client_ip(request_with("junk")) == "203.0.113.5"

    def test_ignores_the_header_unless_trusted(self, settings, request_with):
        settings.TRUST_X_FORWARDED_FOR = False

        assert _client_ip(request_with("198.51.100.7")) == "203.0.113.5"

    def test_takes_the_address_the_web_app_vouches_for(self, settings, request_with):
        settings.BFF_SHARED_SECRET = "bff-secret"
        settings.TRUST_X_FORWARDED_FOR = True

        request = request_with(
            "10.0.0.1", HTTP_X_CLIENT_IP="198.51.100.20", HTTP_X_BFF_SECRET="bff-secret"
        )

        assert _client_ip(request) == "198.51.100.20"

    @pytest.mark.parametrize(("configured", "sent"), [("bff-secret", "guess"), ("", "")])
    def test_ignores_the_web_app_header_without_the_secret(
        self, settings, request_with, configured, sent
    ):
        settings.BFF_SHARED_SECRET = configured

        request = request_with(HTTP_X_CLIENT_IP="198.51.100.20", HTTP_X_BFF_SECRET=sent)

        assert _client_ip(request) == "203.0.113.5"

    def test_ignores_a_vouched_value_that_is_not_an_address(self, settings, request_with):
        settings.BFF_SHARED_SECRET = "bff-secret"

        request = request_with(HTTP_X_CLIENT_IP="junk", HTTP_X_BFF_SECRET="bff-secret")

        assert _client_ip(request) == "203.0.113.5"
