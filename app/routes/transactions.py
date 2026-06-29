from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import Account, Transaction, User
from app.validation import (
    ValidationError,
    require_fields,
    to_minor_units,
    validate_amount,
    validate_phone,
)

transactions_bp = Blueprint("transactions", __name__)


def _get_locked_account(user_id: str) -> Account:
    """Fetch the caller's account with a row lock, for safe balance mutation.

    SELECT ... FOR UPDATE ensures two concurrent requests against the same
    account serialize instead of racing on a read-modify-write of balance.

    NOTE: SQLite (this project's default, for easy local setup) does not
    support real row-level locking — with_for_update() is a no-op here and
    SQLite instead serializes at the database-file level via its own locking,
    which is sufficient for a single dev instance but not for production
    concurrency. On Postgres (the intended production target), this becomes
    a genuine row lock. Don't ship this on SQLite under real concurrent load.
    """
    return (
        Account.query.filter_by(user_id=user_id).with_for_update().one()
    )


@transactions_bp.get("/history")
@jwt_required()
def history():
    user_id = get_jwt_identity()
    account = Account.query.filter_by(user_id=user_id).first()
    if not account:
        return jsonify({"error": "Account not found."}), 404

    page = request.args.get("page", default=1, type=int) or 1
    per_page = request.args.get("perPage", default=20, type=int) or 20
    per_page = max(1, min(per_page, 100))

    query = (
        Transaction.query.filter_by(account_id=account.id)
        .order_by(Transaction.created_at.desc())
    )
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify(
        {
            "transactions": [t.to_dict() for t in items],
            "page": page,
            "perPage": per_page,
            "total": total,
        }
    )


@transactions_bp.post("/deposit")
@jwt_required()
def deposit():
    user_id = get_jwt_identity()
    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["amount"])
    amount = validate_amount(payload["amount"])
    amount_minor = to_minor_units(amount)

    account = _get_locked_account(user_id)
    account.balance_minor += amount_minor

    txn = Transaction(
        account_id=account.id,
        type="deposit",
        amount_minor=amount_minor,
        balance_after_minor=account.balance_minor,
        description=payload.get("description", "Deposit"),
    )
    db.session.add(txn)
    db.session.commit()

    return jsonify({"account": account.to_dict(), "transaction": txn.to_dict()})


@transactions_bp.post("/withdraw")
@jwt_required()
def withdraw():
    user_id = get_jwt_identity()
    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["amount"])
    amount = validate_amount(payload["amount"])
    amount_minor = to_minor_units(amount)

    account = _get_locked_account(user_id)

    if account.balance_minor < amount_minor:
        raise ValidationError("Insufficient funds.", field="amount")

    account.balance_minor -= amount_minor

    txn = Transaction(
        account_id=account.id,
        type="withdrawal",
        amount_minor=amount_minor,
        balance_after_minor=account.balance_minor,
        description=payload.get("description", "Withdrawal"),
    )
    db.session.add(txn)
    db.session.commit()

    return jsonify({"account": account.to_dict(), "transaction": txn.to_dict()})


@transactions_bp.post("/transfer")
@jwt_required()
def transfer():
    user_id = get_jwt_identity()
    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["receiverAccountNumber", "amount"])

    receiver_account_number = str(payload["receiverAccountNumber"]).strip()
    amount = validate_amount(payload["amount"])
    amount_minor = to_minor_units(amount)

    sender_account = Account.query.filter_by(user_id=user_id).first()
    if not sender_account:
        return jsonify({"error": "Account not found."}), 404

    if receiver_account_number == sender_account.account_number:
        raise ValidationError("You cannot transfer to your own account.", field="receiverAccountNumber")

    receiver_account = Account.query.filter_by(
        account_number=receiver_account_number
    ).first()
    if not receiver_account:
        raise ValidationError("Receiver account not found.", field="receiverAccountNumber")

    # Lock both rows in a fixed order (by id) to avoid deadlocks when two
    # transfers happen between the same pair of accounts in opposite directions.
    ids_in_order = sorted([sender_account.id, receiver_account.id])
    locked = {
        acc.id: acc
        for acc in Account.query.filter(Account.id.in_(ids_in_order))
        .with_for_update()
        .all()
    }
    sender_account = locked[sender_account.id]
    receiver_account = locked[receiver_account.id]

    if sender_account.balance_minor < amount_minor:
        raise ValidationError("Insufficient funds.", field="amount")

    sender_account.balance_minor -= amount_minor
    receiver_account.balance_minor += amount_minor

    receiver_user = User.query.get(receiver_account.user_id)
    sender_user = User.query.get(sender_account.user_id)

    outgoing = Transaction(
        account_id=sender_account.id,
        type="transfer_out",
        amount_minor=amount_minor,
        balance_after_minor=sender_account.balance_minor,
        counterparty_account_number=receiver_account.account_number,
        counterparty_name=receiver_user.full_name if receiver_user else None,
        description=payload.get("description", "Transfer sent"),
    )
    incoming = Transaction(
        account_id=receiver_account.id,
        type="transfer_in",
        amount_minor=amount_minor,
        balance_after_minor=receiver_account.balance_minor,
        counterparty_account_number=sender_account.account_number,
        counterparty_name=sender_user.full_name if sender_user else None,
        description=payload.get("description", "Transfer received"),
    )
    db.session.add_all([outgoing, incoming])
    db.session.commit()

    return jsonify({"account": sender_account.to_dict(), "transaction": outgoing.to_dict()})


@transactions_bp.post("/airtime")
@jwt_required()
def airtime():
    user_id = get_jwt_identity()
    payload = request.get_json(silent=True) or {}
    require_fields(payload, ["amount", "phone"])

    amount = validate_amount(payload["amount"])
    phone = validate_phone(payload["phone"])
    amount_minor = to_minor_units(amount)

    account = _get_locked_account(user_id)

    if account.balance_minor < amount_minor:
        raise ValidationError("Insufficient funds.", field="amount")

    account.balance_minor -= amount_minor

    txn = Transaction(
        account_id=account.id,
        type="airtime",
        amount_minor=amount_minor,
        balance_after_minor=account.balance_minor,
        counterparty_account_number=phone,
        description=f"Airtime top-up for {phone}",
    )
    db.session.add(txn)
    db.session.commit()

    return jsonify({"account": account.to_dict(), "transaction": txn.to_dict()})
