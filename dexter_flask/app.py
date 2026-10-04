"""Flask application factory."""

from __future__ import annotations

import os

from flask import Flask

from dexter_flask.config import get_settings
from dexter_flask.cron_scheduler import start_cron_scheduler
from dexter_flask.routes.agent_api import agent_bp
from dexter_flask.routes.health import health_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    app.register_blueprint(agent_bp)
    if os.environ.get("DEXTER_DISABLE_CRON") != "1":
        start_cron_scheduler()
    return app


def _get_run_kwargs() -> dict:
    """Return the keyword arguments that should be passed to app.run().

    Extracted as a pure helper so it can be unit-tested without starting the
    server.  Default host is ``127.0.0.1`` (localhost only).  Set
    ``FLASK_HOST=0.0.0.0`` only when non-local access is intentional (e.g.
    inside a container behind a reverse proxy).  For production traffic always
    use a proper WSGI server such as Gunicorn.
    """
    return {
        "host": os.environ.get("FLASK_HOST", "127.0.0.1"),
        "port": int(os.environ.get("PORT", "5050")),
        # FLASK_DEBUG enables Werkzeug's interactive debugger — never set to 1
        # on a non-local interface or in production.
        "debug": os.environ.get("FLASK_DEBUG") == "1",
    }


app = create_app()

if __name__ == "__main__":
    app.run(**_get_run_kwargs())

