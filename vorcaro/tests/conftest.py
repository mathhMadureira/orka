import pytest

from vorcaro.data.providers import synthetic


@pytest.fixture(scope="session")
def rw():
    return synthetic(1200, seed=11, ar=0.0)


@pytest.fixture(scope="session")
def reverting():
    return synthetic(1200, seed=2, ar=-0.3)
