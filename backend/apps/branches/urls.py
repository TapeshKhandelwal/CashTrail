from rest_framework.routers import SimpleRouter

from .views import BranchViewSet

router = SimpleRouter(trailing_slash=True)
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = [*router.urls]
