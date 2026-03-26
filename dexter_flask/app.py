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


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
