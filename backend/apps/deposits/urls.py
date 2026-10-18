from rest_framework.routers import SimpleRouter

from .views import BankAccountViewSet, DepositViewSet, GatewaySettlementViewSet

router = SimpleRouter(trailing_slash=True)
router.register("bank-accounts", BankAccountViewSet, basename="bank-account")
router.register("deposits", DepositViewSet, basename="deposit")
router.register("gateway-settlements", GatewaySettlementViewSet, basename="gateway-settlement")

urlpatterns = [*router.urls]
