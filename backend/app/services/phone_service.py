"""Phone number validation and normalization.

Uses Google's libphonenumber (via the `phonenumbers` package) to validate
and normalize numbers into E.164 format, e.g. +919876543210.

Rules:
- Numbers with an international prefix (+91..., 0091...) are validated as-is.
- Bare national numbers (e.g. 9876543210) are interpreted against
  DEFAULT_REGION (default IN).
- Anything that cannot be parsed as a valid number is rejected.
"""

from dataclasses import dataclass

import phonenumbers
from phonenumbers import NumberParseException

from app.core.config import settings


@dataclass
class PhoneValidationResult:
    original: str
    normalized: str | None
    valid: bool
    reason: str | None = None


def normalize_phone(raw: str, region: str | None = None) -> PhoneValidationResult:
    """Validate and normalize a phone number to E.164.

    Returns a PhoneValidationResult; `normalized` is only set when valid.
    """
    if raw is None:
        return PhoneValidationResult("", None, False, "missing phone number")
    original = str(raw).strip()
    if not original:
        return PhoneValidationResult(original, None, False, "missing phone number")

    region = region or settings.DEFAULT_REGION

    try:
        if original.startswith("+"):
            number = phonenumbers.parse(original, None)
        elif original.startswith("00"):
            number = phonenumbers.parse("+" + original[2:], None)
        else:
            number = phonenumbers.parse(original, region)
    except NumberParseException:
        return PhoneValidationResult(original, None, False, "malformed phone number")

    if not phonenumbers.is_possible_number(number):
        return PhoneValidationResult(original, None, False, "impossible phone number")
    if not phonenumbers.is_valid_number(number):
        return PhoneValidationResult(original, None, False, "invalid phone number")

    return PhoneValidationResult(
        original,
        phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
        True,
    )


def is_valid_phone(raw: str, region: str | None = None) -> bool:
    return normalize_phone(raw, region).valid
