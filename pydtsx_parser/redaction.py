"""Sensitive data redaction module for SSIS Parser output.

This module provides post-processing redaction of sensitive values in the
parsed output dictionary. It handles three categories of sensitive data:

1. Elements marked with Sensitive="1" attribute (DTS:Sensitive, SSIS:Sensitive)
   - These already appear in the parsed output as {"value": ..., "sensitive": true}
   - The value is replaced with the redaction placeholder

2. Fields whose key name matches sensitive patterns (password, pwd, orapassword)
   - Case-insensitive matching against field names in the output dict

3. Connection string key-value pairs containing password/pwd
   - Parses semicolon-separated connection strings and redacts password values

Data flow column names (cached_name, name in column contexts) are explicitly
excluded from redaction even if they contain sensitive-looking patterns, as
they represent schema metadata rather than credential values.
"""

import copy
import re
from typing import Any

# Patterns that indicate a field contains sensitive data (case-insensitive)
SENSITIVE_FIELD_PATTERNS = ["password", "pwd", "orapassword"]

# Placeholder for redacted values
REDACTION_PLACEHOLDER = "[SENSITIVE - REDACTED]"

# Keys in column-context dicts that should NOT be redacted even if their
# values match sensitive patterns. These represent schema metadata.
_COLUMN_CONTEXT_KEYS = frozenset(
    {
        "cached_name",
        "name",
        "column_name",
    }
)

# Keys that indicate a dict represents a data flow column definition
_COLUMN_INDICATOR_KEYS = frozenset(
    {
        "cached_data_type",
        "cached_length",
        "cached_precision",
        "cached_scale",
        "cached_codepage",
        "lineage_id",
        "data_type",
        "length",
        "precision",
        "scale",
        "code_page",
        "external_metadata_column_id",
        "error_row_disposition",
        "truncation_row_disposition",
        "sort_key_position",
        "sort_order",
    }
)

# Connection string keys whose values should be redacted
_CONNECTION_STRING_SENSITIVE_KEYS = re.compile(r"(password|pwd)", re.IGNORECASE)


def redact(data: dict) -> tuple[dict, int]:
    """Walk the output dict, redact sensitive values, return (redacted_data, count).

    Performs a deep copy of the input data and then recursively walks the
    structure to find and redact sensitive values. Three types of redaction:

    1. Fields already marked as sensitive ({"value": ..., "sensitive": true})
    2. Fields whose key matches SENSITIVE_FIELD_PATTERNS
    3. Connection string values containing password/pwd key-value pairs

    Data flow column names are excluded from redaction.

    Args:
        data: The parsed output dictionary to redact.

    Returns:
        A tuple of (redacted copy of data, total number of redactions performed).
    """
    redacted = copy.deepcopy(data)
    count = _walk_and_redact(redacted, parent_is_column=False)
    return redacted, count


def is_sensitive_field(field_name: str) -> bool:
    """Check if a field name matches known sensitive patterns.

    Performs case-insensitive matching against SENSITIVE_FIELD_PATTERNS.

    Args:
        field_name: The field name to check.

    Returns:
        True if the field name matches any sensitive pattern.
    """
    field_lower = field_name.lower()
    return any(pattern in field_lower for pattern in SENSITIVE_FIELD_PATTERNS)


def is_sensitive_attribute(attributes: dict) -> bool:
    """Check if element has Sensitive='1' attribute.

    Looks for Sensitive, DTS:Sensitive, or SSIS:Sensitive attributes
    with value "1" in the provided attributes dictionary.

    Args:
        attributes: Dictionary of element attributes.

    Returns:
        True if any Sensitive attribute has value "1".
    """
    sensitive_keys = ["Sensitive", "DTS:Sensitive", "SSIS:Sensitive"]
    for key in sensitive_keys:
        if attributes.get(key) == "1":
            return True
    # Also check for lowercase variants and namespace-stripped keys
    for key, value in attributes.items():
        key_lower = key.lower()
        if key_lower.endswith("sensitive") and value == "1":
            return True
    return False


def _is_column_dict(d: dict) -> bool:
    """Determine if a dictionary represents a data flow column definition.

    A column dict is identified by the presence of column-specific metadata
    keys like cached_data_type, lineage_id, data_type, etc.

    Args:
        d: Dictionary to check.

    Returns:
        True if the dict appears to be a column definition.
    """
    return bool(set(d.keys()) & _COLUMN_INDICATOR_KEYS)


def _redact_connection_string(conn_str: str) -> tuple[str, int]:
    """Parse a connection string and redact sensitive key-value pairs.

    Connection strings are semicolon-separated key=value pairs.
    Any pair where the key contains "password" or "pwd" (case-insensitive)
    has its value replaced with the redaction placeholder.

    Args:
        conn_str: The connection string to process.

    Returns:
        Tuple of (redacted connection string, count of redactions).
    """
    if not conn_str or "=" not in conn_str:
        return conn_str, 0

    parts = conn_str.split(";")
    redaction_count = 0
    result_parts = []

    for part in parts:
        if "=" in part:
            key = part.partition("=")[0]
            if _CONNECTION_STRING_SENSITIVE_KEYS.search(key.strip()):
                result_parts.append(f"{key}={REDACTION_PLACEHOLDER}")
                redaction_count += 1
            else:
                result_parts.append(part)
        else:
            result_parts.append(part)

    return ";".join(result_parts), redaction_count


def _walk_and_redact(obj: Any, parent_is_column: bool = False) -> int:
    """Recursively walk a data structure and redact sensitive values in place.

    Args:
        obj: The object to walk (dict, list, or scalar).
        parent_is_column: Whether the current context is within a column definition.

    Returns:
        Total number of redactions performed.
    """
    if isinstance(obj, dict):
        return _redact_dict(obj, parent_is_column)
    elif isinstance(obj, list):
        return _redact_list(obj, parent_is_column)
    return 0


def _redact_dict(d: dict, parent_is_column: bool = False) -> int:
    """Redact sensitive values within a dictionary.

    Handles three cases:
    1. Dicts with "sensitive": true and a "value" key - redact the value
    2. Keys matching sensitive field patterns - redact the value
    3. Connection string values - parse and redact password fields

    Args:
        d: Dictionary to process in place.
        parent_is_column: Whether this dict is within a column context.

    Returns:
        Count of redactions performed.
    """
    count = 0
    is_column = parent_is_column or _is_column_dict(d)

    # Case 1: Already-marked sensitive fields (from extractors)
    # These have the form {"value": "...", "sensitive": true}
    if d.get("sensitive") is True and "value" in d:
        if d["value"] != REDACTION_PLACEHOLDER:
            d["value"] = REDACTION_PLACEHOLDER
            count += 1
        # Don't recurse further into this dict since it's a leaf value
        return count

    keys = list(d.keys())
    for key in keys:
        value = d[key]

        # Skip column name fields in column-context dicts
        if is_column and key in _COLUMN_CONTEXT_KEYS:
            continue

        # Case 2: Field name matches sensitive patterns
        if is_sensitive_field(key) and not is_column:
            if isinstance(value, dict):
                # Already structured as {"value": ..., "sensitive": ...}
                if "value" in value:
                    if value.get("value") != REDACTION_PLACEHOLDER:
                        value["value"] = REDACTION_PLACEHOLDER
                        value["sensitive"] = True
                        count += 1
                else:
                    # Replace entire dict value
                    d[key] = {"value": REDACTION_PLACEHOLDER, "sensitive": True}
                    count += 1
            elif isinstance(value, str):
                d[key] = {"value": REDACTION_PLACEHOLDER, "sensitive": True}
                count += 1
            elif isinstance(value, (int, float, bool)):
                # Numeric/boolean sensitive values
                d[key] = {"value": REDACTION_PLACEHOLDER, "sensitive": True}
                count += 1
            else:
                # For lists or other types, recurse
                count += _walk_and_redact(value, is_column)
            continue

        # Case 3: Connection string fields - parse and redact password parts
        if key == "connection_string" and isinstance(value, str):
            redacted_str, redact_count = _redact_connection_string(value)
            if redact_count > 0:
                d[key] = redacted_str
                count += redact_count
            continue

        # Recurse into nested structures
        count += _walk_and_redact(value, is_column)

    return count


def _redact_list(lst: list, parent_is_column: bool = False) -> int:
    """Redact sensitive values within a list.

    Args:
        lst: List to process in place.
        parent_is_column: Whether this list is within a column context.

    Returns:
        Count of redactions performed.
    """
    count = 0
    for item in lst:
        count += _walk_and_redact(item, parent_is_column)
    return count
