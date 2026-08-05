from flask import Flask

from .config import Config
from .database import db
from .routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        from .models import User  # noqa: F401

        db.create_all()

    return app
