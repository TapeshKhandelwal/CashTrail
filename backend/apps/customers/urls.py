from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AgentCustomerListView, CustomerViewSet

router = SimpleRouter(trailing_slash=True)
router.register("customers", CustomerViewSet, basename="customer")

urlpatterns = [
    path("agent/customers/", AgentCustomerListView.as_view(), name="agent-customers"),
    *router.urls,
]
