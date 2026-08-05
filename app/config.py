import os

from dotenv import load_dotenv

# For local development only. In ECS production, secrets come from env vars.
load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "local-dev-secret")

    db_user = os.getenv("DB_USER", "flask_user")
    db_password = os.getenv("DB_PASSWORD", "flask_password")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "flask_auth")
    db_sslmode = os.getenv("DB_SSLMODE", "prefer")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode={db_sslmode}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
