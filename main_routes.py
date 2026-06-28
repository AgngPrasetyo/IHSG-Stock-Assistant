"""Public non-API routes."""

from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def index() -> str:
    """Render the public landing page."""
    return render_template("index.html")


@main_bp.get("/analysis")
def analysis() -> str:
    """Render the focused stock analysis experience."""
    return render_template("analysis.html")
