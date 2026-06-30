"""Flask application factory for the stock decision assistant."""

from __future__ import annotations

import os

from flask import Flask

from routes.api_routes import api_bp
from routes.main_routes import main_bp


def create_app(test_config: dict | None = None) -> Flask:
    """Create the web application without running analysis during import."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "development-only-secret-key"),
        ENV=os.getenv("FLASK_ENV", "production"),
    )
    if test_config is not None:
        app.config.update(test_config)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV", "").strip().lower() == "development")
