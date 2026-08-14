"""Message template personalization.

Supported variables (case-insensitive, whitespace tolerated):

    {{first_name}} {{last_name}} {{phone}} {{email}} {{company}} {{notes}}

Unknown variables are detected and reported - they are never silently
left in a message.
"""

import re
from dataclasses import dataclass, field

SUPPORTED_VARIABLES = {
    "first_name",
    "last_name",
    "phone",
    "email",
    "company",
    "notes",
}

VARIABLE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@dataclass
class TemplateAnalysis:
    variables_found: list[str] = field(default_factory=list)
    unsupported_variables: list[str] = field(default_factory=list)


def extract_variables(message: str) -> TemplateAnalysis:
    """Find {{variables}} in a template, split into supported/unsupported."""
    found: list[str] = []
    unsupported: list[str] = []
    for match in VARIABLE_RE.finditer(message or ""):
        name = match.group(1).lower()
        if name in SUPPORTED_VARIABLES:
            if name not in found:
                found.append(name)
        else:
            unsupported.append(match.group(1))
    return TemplateAnalysis(found, unsupported)


def get_field_value(contact, field: str) -> str:
    """Resolve a variable name against a Contact-like object."""
    field = field.lower()
    if field == "first_name":
        return contact.first_name or ""
    if field == "last_name":
        return contact.last_name or ""
    if field == "phone":
        return contact.phone or ""
    if field == "email":
        return contact.email or ""
    if field == "company":
        return contact.company or ""
    if field == "notes":
        return contact.notes or ""
    return ""


def personalize(message: str, contact) -> tuple[str, list[str]]:
    """Replace supported variables with the contact's values.

    Returns (personalized_message, missing_fields) where missing_fields
    lists variables whose value was empty for this contact.
    """
    missing: list[str] = []

    def replacer(match: re.Match) -> str:
        name = match.group(1).lower()
        if name not in SUPPORTED_VARIABLES:
            # Keep unsupported variables untouched; caller decides.
            return match.group(0)
        value = get_field_value(contact, name)
        if not value:
            missing.append(name)
        return value

    personalized = VARIABLE_RE.sub(replacer, message or "")
    return personalized, missing


def preview(message: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Personalize against a plain dict of values (used for previews)."""

    class _DictContact:
        pass

    contact = _DictContact()
    for key in SUPPORTED_VARIABLES:
        setattr(contact, key, values.get(key, ""))
    return personalize(message, contact)
