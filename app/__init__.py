import os
from datetime import timedelta

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from app.extensions import db, jwt

load_dotenv()


def _normalize_database_url(url: str) -> str:
    """Most hosts (Render, Heroku-style providers) hand out connection
    strings starting with postgres://, but SQLAlchemy 1.4+ requires the
    postgresql:// scheme. Without this, deploys crash on the first request
    that touches the database with a confusing dialect error."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
    app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalize_database_url(
        os.environ.get("DATABASE_URL", "sqlite:///zenith.db")
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Postgres connections can go stale/get dropped by the host's connection
    # pooler while idle; pre-pinging avoids "server closed the connection
    # unexpectedly" errors on the first request after a quiet period.
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", 30))
    )
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(
        days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", 7))
    )
    app.config["JWT_TOKEN_LOCATION"] = ["headers"]

    db.init_app(app)
    jwt.init_app(app)

    frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
    CORS(app, resources={r"/api/*": {"origins": frontend_origin}}, supports_credentials=True)

    from app.routes.auth import auth_bp
    from app.routes.accounts import accounts_bp
    from app.routes.transactions import transactions_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(accounts_bp, url_prefix="/api/accounts")
    app.register_blueprint(transactions_bp, url_prefix="/api/transactions")

    from app.errors import register_error_handlers

    register_error_handlers(app)

    with app.app_context():
        db.create_all()
        from app.seed import seed_demo_data

        seed_demo_data()

    return app
