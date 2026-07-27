import pytest
from persistence.engine import session_scope
from persistence.models.oss import Outage


@pytest.fixture
def session():
    with session_scope() as s:
        yield s


@pytest.fixture
def make_outage(session):
    created = []

    def _factory(**kwargs):
        outage = Outage(**kwargs)
        session.add(outage)
        session.flush()
        created.append(outage)
        return outage

    yield _factory

    for o in created:
        try:
            session.delete(o)
            session.flush()
        except Exception:
            pass
