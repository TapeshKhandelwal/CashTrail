from rest_framework.routers import SimpleRouter

from .views import CollectionViewSet

router = SimpleRouter(trailing_slash=True)
router.register("collections", CollectionViewSet, basename="collection")

urlpatterns = [*router.urls]
