"""Phone validation/normalization unit tests."""

import pytest

from app.services.phone_service import normalize_phone


def test_national_number_with_default_region():
    result = normalize_phone("9876543210")
    assert result.valid
    assert result.normalized == "+919876543210"


def test_international_prefix():
    result = normalize_phone("+919876543210")
    assert result.valid
    assert result.normalized == "+919876543210"


def test_leading_zeros_prefix():
    result = normalize_phone("00919876543210")
    assert result.valid
    assert result.normalized == "+919876543210"


def test_consistent_storage():
    """Different input spellings must normalize identically."""
    variants = ["+91 98765 43210", "+919876543210", "0091 9876543210", "98765 43210"]
    normalized = {normalize_phone(v).normalized for v in variants}
    assert normalized == {"+919876543210"}


def test_explicit_region():
    result = normalize_phone("415 555 2671", region="US")
    assert result.valid
    assert result.normalized == "+14155552671"


def test_empty_number():
    assert not normalize_phone("").valid
    assert not normalize_phone("   ").valid
    assert not normalize_phone(None).valid


def test_malformed_number():
    assert not normalize_phone("not-a-number").valid
    assert not normalize_phone("abc123").valid


def test_impossible_number():
    assert not normalize_phone("+919876543").valid  # too short


def test_unknown_country_code():
    assert not normalize_phone("+999123456789").valid


def test_invalid_number_reason():
    result = normalize_phone("")
    assert result.reason == "missing phone number"
