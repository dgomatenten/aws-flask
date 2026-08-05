import os

from app import create_app
from app.database import db
from app.models import User


app = create_app()


with app.app_context():
    username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123")

    if not username or not password:
        raise ValueError("BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD are required")

    existing = User.query.filter_by(username=username).first()
    if existing:
        print(f"User '{username}' already exists.")
    else:
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Created user '{username}'.")
