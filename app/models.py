import uuid
from datetime import datetime, timezone
from decimal import Decimal

import bcrypt

from app.extensions import db


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    account = db.relationship(
        "Account", backref="owner", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password: str) -> None:
        hashed = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt(rounds=12))
        self.password_hash = hashed.decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.checkpw(
            raw_password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def to_dict(self):
        return {
            "id": self.id,
            "fullName": self.full_name,
            "email": self.email,
            "createdAt": self.created_at.isoformat(),
        }


class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False, unique=True
    )
    account_number = db.Column(db.String(20), nullable=False, unique=True, index=True)
    # Stored in minor units (kobo) as an integer to avoid float rounding errors.
    balance_minor = db.Column(db.BigInteger, nullable=False, default=0)
    currency = db.Column(db.String(3), nullable=False, default="NGN")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        db.CheckConstraint("balance_minor >= 0", name="ck_balance_nonnegative"),
    )

    @property
    def balance(self) -> Decimal:
        return Decimal(self.balance_minor) / Decimal(100)

    def to_dict(self):
        return {
            "id": self.id,
            "accountNumber": self.account_number,
            "balance": str(self.balance),
            "currency": self.currency,
        }


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    account_id = db.Column(
        db.String(36), db.ForeignKey("accounts.id"), nullable=False, index=True
    )
    type = db.Column(db.String(20), nullable=False)  # deposit, withdrawal, transfer_out, transfer_in, airtime
    amount_minor = db.Column(db.BigInteger, nullable=False)
    balance_after_minor = db.Column(db.BigInteger, nullable=False)
    counterparty_account_number = db.Column(db.String(20), nullable=True)
    counterparty_name = db.Column(db.String(120), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="completed")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    account = db.relationship("Account", backref="transactions")

    @property
    def amount(self) -> Decimal:
        return Decimal(self.amount_minor) / Decimal(100)

    @property
    def balance_after(self) -> Decimal:
        return Decimal(self.balance_after_minor) / Decimal(100)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "amount": str(self.amount),
            "balanceAfter": str(self.balance_after),
            "counterpartyAccountNumber": self.counterparty_account_number,
            "counterpartyName": self.counterparty_name,
            "description": self.description,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
        }
