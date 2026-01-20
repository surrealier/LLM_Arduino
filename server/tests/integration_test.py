import os
import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 to enable integration tests.",
)


def test_integration_placeholder():
    assert True
