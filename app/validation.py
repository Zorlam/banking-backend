import re
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")

MIN_AMOUNT = Decimal("1.00")
MAX_AMOUNT = Decimal("5000000.00")  # ₦5,000,000 per-transaction ceiling for this demo


class ValidationError(Exception):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.field = field


def require_fields(payload: dict, fields: list[str]) -> None:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.")
    missing = [f for f in fields if not str(payload.get(f, "")).strip()]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}.")


def validate_email(email: str) -> str:
    email = email.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address.", field="email")
    return email


def validate_password(password: str) -> str:
    if len(password) < 8:
        raise ValidationError(
            "Password must be at least 8 characters long.", field="password"
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        raise ValidationError(
            "Password must include at least one letter and one number.",
            field="password",
        )
    return password


def validate_full_name(name: str) -> str:
    name = name.strip()
    if len(name) < 2 or len(name) > 120:
        raise ValidationError("Enter a valid full name.", field="fullName")
    return name


def validate_amount(raw_amount) -> Decimal:
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Amount must be a valid number.", field="amount")

    # Reject more than 2 decimal places (no fractional kobo).
    if amount != amount.quantize(Decimal("0.01")):
        raise ValidationError("Amount cannot have more than 2 decimal places.", field="amount")

    if amount < MIN_AMOUNT:
        raise ValidationError(f"Amount must be at least ₦{MIN_AMOUNT}.", field="amount")
    if amount > MAX_AMOUNT:
        raise ValidationError(f"Amount cannot exceed ₦{MAX_AMOUNT:,}.", field="amount")

    return amount


def validate_phone(phone: str) -> str:
    phone = phone.strip()
    if not PHONE_RE.match(phone):
        raise ValidationError("Enter a valid phone number.", field="phone")
    return phone


def to_minor_units(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())
