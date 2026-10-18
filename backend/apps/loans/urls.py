from rest_framework.routers import SimpleRouter

from .views import LoanViewSet

router = SimpleRouter(trailing_slash=True)
router.register("loans", LoanViewSet, basename="loan")

urlpatterns = [*router.urls]
