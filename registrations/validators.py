import re

from django.core.exceptions import ValidationError


PHONE_ERROR = (
    "Введите российский номер: 10 цифр, начиная с 9, "
    "или 11 цифр, начиная с 7 или 8."
)


def normalize_russian_phone(value: str) -> str:
    """Validate and normalize a Russian mobile number for storage."""
    raw = value or ""
    if not re.fullmatch(r"\s*\+?[0-9][0-9\s()\-]*\s*", raw):
        raise ValidationError(PHONE_ERROR, code="invalid_phone")
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits.startswith("9"):
        national = digits
    elif len(digits) == 11 and digits[0] in "78":
        national = digits[1:]
    else:
        raise ValidationError(PHONE_ERROR, code="invalid_phone")
    return f"+7 {national[:3]} {national[3:6]}-{national[6:8]}-{national[8:]}"
