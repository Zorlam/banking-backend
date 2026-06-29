import random

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app.extensions import db
from app.models import User, Account
from app.validation import (
    ValidationError,
    require_fields,
    validate_email,
    validate_full_name,
    validate_password,
)

auth_bp = Blueprint("auth", __name__)


def _generate_account_number() -> str:
    while True:
        candidate = "".join(random.choices("0123456789", k=10))
        if not Account.query.filter_by(account_number=candidate).first():
            return candidate


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["fullName", "email", "password"])

    full_name = validate_full_name(payload["fullName"])
    email = validate_email(payload["email"])
    password = validate_password(payload["password"])

    if User.query.filter_by(email=email).first():
        raise ValidationError("An account with this email already exists.", field="email")

    user = User(full_name=full_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    account = Account(user_id=user.id, account_number=_generate_account_number())
    db.session.add(account)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify(
        {
            "user": user.to_dict(),
            "account": account.to_dict(),
            "accessToken": access_token,
            "refreshToken": refresh_token,
        }
    ), 201


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["email", "password"])

    email = payload["email"].strip().lower()
    password = payload["password"]

    user = User.query.filter_by(email=email).first()
    # Constant-shape response whether the email exists or not, to avoid
    # leaking which emails are registered.
    if not user or not user.check_password(password):
        raise ValidationError("Invalid email or password.", field="form")

    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)

    return jsonify(
        {
            "user": user.to_dict(),
            "account": user.account.to_dict(),
            "accessToken": access_token,
            "refreshToken": refresh_token,
        }
    )


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    new_access_token = create_access_token(identity=identity)
    return jsonify({"accessToken": new_access_token})


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"user": user.to_dict(), "account": user.account.to_dict()})
