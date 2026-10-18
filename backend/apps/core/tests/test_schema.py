import pytest

from apps.core.schema import error_responses


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 422, 429, 502])
def test_every_error_status_used_by_the_api_is_described(status_code):
    (response,) = error_responses(status_code).values()

    assert response.description
