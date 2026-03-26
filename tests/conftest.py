import os

import pytest


# Prevent background APScheduler from starting during tests.
# Important: dexter_flask.app has module-level initialization.
os.environ.setdefault("DEXTER_DISABLE_CRON", "1")


@pytest.fixture(autouse=True)
def _clear_sessions() -> None:
    # Keep tests isolated; session history is stored in-process.
    try:
        from dexter_flask.services import sessions as sessions_mod

        sessions_mod._sessions.clear()
    except Exception:
        # If modules aren't importable yet, don't fail collection.
        pass
