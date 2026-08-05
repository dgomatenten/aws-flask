import json
import os
from typing import Any

from app import create_app
from app.database import db
from app.models import User

app = create_app()


def parse_default_users() -> list[dict[str, Any]]:
    raw = os.getenv("DEFAULT_USERS_JSON")
    if raw:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("DEFAULT_USERS_JSON must be a JSON array")
        return data

    return [
        {"username": "admin", "password": os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")},
        {"username": "developer", "password": os.getenv("DEFAULT_DEVELOPER_PASSWORD", "dev123")},
    ]


with app.app_context():
    users = parse_default_users()

    created = 0
    skipped = 0

    for item in users:
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", ""))

        if not username or not password:
            print("Skipping invalid record. username and password are required.")
            skipped += 1
            continue

        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"Skipping '{username}' (already exists)")
            skipped += 1
            continue

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        created += 1

    db.session.commit()
    print(f"Done. created={created}, skipped={skipped}")
