from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import User
from app.validation import ValidationError, require_fields, validate_password

accounts_bp = Blueprint("accounts", __name__)


@accounts_bp.get("/me")
@jwt_required()
def get_my_account():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"account": user.account.to_dict()})


@accounts_bp.post("/change-password")
@jwt_required()
def change_password():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found."}), 404

    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["currentPassword", "newPassword"])

    if not user.check_password(payload["currentPassword"]):
        raise ValidationError("Current password is incorrect.", field="currentPassword")

    new_password = validate_password(payload["newPassword"])
    if user.check_password(new_password):
        raise ValidationError(
            "New password must be different from the current password.",
            field="newPassword",
        )

    user.set_password(new_password)
    db.session.commit()

    return jsonify({"message": "Password changed successfully."})
