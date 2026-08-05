from flask import Blueprint, jsonify, request, session
from sqlalchemy import text

from .database import db
from .models import User

bp = Blueprint("api", __name__)


@bp.route("/health", methods=["GET"])
def healthcheck():
    try:
        db.session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    status_code = 200 if db_ok else 503
    return (
        jsonify(
            {
                "status": "ok" if db_ok else "degraded",
                "service": "aws-flask-auth",
                "database": "up" if db_ok else "down",
            }
        ),
        status_code,
    )


@bp.route("/auth/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username", "").strip()
    password = payload.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if user is None or not user.verify_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    session["user_id"] = user.id
    session["username"] = user.username

    return jsonify({"message": "login successful", "username": user.username}), 200


@bp.route("/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "logout successful"}), 200


@bp.route("/auth/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"authenticated": False}), 401

    return (
        jsonify(
            {
                "authenticated": True,
                "user_id": session["user_id"],
                "username": session.get("username"),
            }
        ),
        200,
    )
