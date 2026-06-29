import random

from app.extensions import db
from app.models import User, Account


def _generate_account_number() -> str:
    while True:
        candidate = "".join(random.choices("0123456789", k=10))
        if not Account.query.filter_by(account_number=candidate).first():
            return candidate


def seed_demo_data():
    """Creates demo users on first run only. Safe to call every startup."""
    if User.query.first():
        return

    demo_users = [
        {
            "full_name": "Daniel Chizorlam Jackson",
            "email": "daniel@example.com",
            "password": "Prayer123",
            "balance": "1000.00",
        },
        {
            "full_name": "Sharon Adeyemi",
            "email": "sharon@example.com",
            "password": "Sunrise123",
            "balance": "500.00",
        },
    ]

    for data in demo_users:
        user = User(full_name=data["full_name"], email=data["email"])
        user.set_password(data["password"])
        db.session.add(user)
        db.session.flush()  # assign user.id

        account = Account(
            user_id=user.id,
            account_number=_generate_account_number(),
            balance_minor=int(float(data["balance"]) * 100),
        )
        db.session.add(account)

    db.session.commit()
