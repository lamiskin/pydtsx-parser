"""Property-based tests for sensitive data redaction.

Uses Hypothesis to verify correctness properties of the redaction module
by generating data structures with sensitive values in various positions
and verifying the redaction logic.

# Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness
# Feature: pydtsx-parser, Property 10: Schema Column Names Not Redacted

**Validates: Requirements 13.1, 13.2, 13.3, 13.4**
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydtsx_parser.redaction import (
    REDACTION_PLACEHOLDER,
    SENSITIVE_FIELD_PATTERNS,
    redact,
)

# --- Strategies ---

# Strategy for non-empty string values (representing sensitive credential values)
credential_value = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
).filter(lambda s: s != REDACTION_PLACEHOLDER)

# Strategy for safe key names that are NOT sensitive
safe_key = st.sampled_from(
    [
        "server_name",
        "user_name",
        "description",
        "object_name",
        "creation_name",
        "ref_id",
        "dts_id",
        "host",
        "port",
        "database",
        "schema",
        "timeout",
        "retry_count",
    ]
)

# Strategy for sensitive field name variants
sensitive_field_name = st.sampled_from(
    [
        "password",
        "Password",
        "PASSWORD",
        "pwd",
        "Pwd",
        "PWD",
        "orapassword",
        "OraPassword",
        "ORAPASSWORD",
        "user_password",
        "db_password",
        "admin_pwd",
        "oracle_password",
        "connection_pwd",
    ]
)

# Strategy for connection string password key variants
conn_str_password_key = st.sampled_from(
    [
        "Password",
        "password",
        "PWD",
        "pwd",
        "Pwd",
    ]
)

# Strategy for non-sensitive connection string keys
conn_str_safe_key = st.sampled_from(
    [
        "Server",
        "Data Source",
        "Initial Catalog",
        "User ID",
        "Integrated Security",
        "Provider",
        "Persist Security Info",
        "Timeout",
    ]
)

# Strategy for column name values that look like they could be passwords
password_like_column_name = st.sampled_from(
    [
        "PASSWORD",
        "PWD",
        "USER_PASSWORD",
        "ENCRYPTED_PWD",
        "PASSWORD_HASH",
        "SPASSWORD",
        "OLD_PASSWORD",
        "Password",
        "Pwd",
        "password_field",
    ]
)


# --- Composite strategies ---


@st.composite
def sensitive_marked_dict(draw):
    """Generate a dict containing {"value": ..., "sensitive": true} entries.

    These represent elements that were marked with Sensitive="1" during extraction.
    """
    val = draw(credential_value)
    return {"value": val, "sensitive": True}


@st.composite
def dict_with_sensitive_field_names(draw):
    """Generate a dict with keys matching sensitive patterns (password, pwd, orapassword).

    The values are plain strings that should be redacted based on field name matching.
    """
    num_sensitive = draw(st.integers(min_value=1, max_value=5))
    num_safe = draw(st.integers(min_value=0, max_value=5))

    result = {}
    sensitive_keys_used = []

    for _ in range(num_sensitive):
        key = draw(sensitive_field_name)
        val = draw(credential_value)
        result[key] = val
        sensitive_keys_used.append(key)

    for _ in range(num_safe):
        key = draw(safe_key)
        val = draw(credential_value)
        result[key] = val

    return result, sensitive_keys_used


@st.composite
def connection_string_with_password(draw):
    """Generate a connection string containing password/pwd key-value pairs."""
    num_safe_parts = draw(st.integers(min_value=1, max_value=4))
    num_sensitive_parts = draw(st.integers(min_value=1, max_value=2))

    parts = []
    sensitive_count = 0

    for _ in range(num_safe_parts):
        key = draw(conn_str_safe_key)
        val = draw(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("L", "N"), whitelist_characters="._-/\\:"
                ),
                min_size=1,
                max_size=20,
            )
        )
        parts.append(f"{key}={val}")

    for _ in range(num_sensitive_parts):
        key = draw(conn_str_password_key)
        val = draw(credential_value)
        parts.append(f"{key}={val}")
        sensitive_count += 1

    # Shuffle parts so sensitive ones aren't always last
    shuffled = draw(st.permutations(parts))
    conn_str = ";".join(shuffled)

    return conn_str, sensitive_count


@st.composite
def nested_dict_with_sensitive_values(draw):
    """Generate a nested dict structure with sensitive values at various depths."""
    # Top-level sensitive field
    top_key = draw(sensitive_field_name)
    top_val = draw(credential_value)

    # Nested sensitive field within a sub-dict
    nested_key = draw(sensitive_field_name)
    nested_val = draw(credential_value)

    # A pre-marked sensitive entry
    marked_val = draw(credential_value)

    data = {
        top_key: top_val,
        "properties": {
            nested_key: nested_val,
            "server_name": "some-server",
        },
        "marked_field": {"value": marked_val, "sensitive": True},
        "safe_field": "not-sensitive",
    }

    # Count expected redactions: top_key field + nested_key field + marked_field
    expected_count = 3

    return data, expected_count


@st.composite
def column_context_dict(draw):
    """Generate a dict that represents a data flow column with password-like name.

    These should NOT be redacted since they are schema metadata.
    """
    col_name = draw(password_like_column_name)

    # Include column indicator keys to mark this as a column context
    indicator = draw(
        st.sampled_from(
            [
                ("cached_data_type", "130"),
                ("lineage_id", "42"),
                ("data_type", "131"),
            ]
        )
    )

    col_dict = {
        "name": col_name,
        "cached_name": col_name,
        indicator[0]: indicator[1],
        "precision": "10",
        "scale": "0",
    }

    return col_dict


@st.composite
def column_in_list_context(draw):
    """Generate a data flow component structure with columns that have password-like names."""
    num_columns = draw(st.integers(min_value=1, max_value=5))
    columns = []

    for _ in range(num_columns):
        col_name = draw(password_like_column_name)
        col = {
            "name": col_name,
            "cached_name": col_name,
            "data_type": "130",
            "length": "50",
            "precision": "0",
            "scale": "0",
            "code_page": "0",
            "lineage_id": str(draw(st.integers(min_value=1, max_value=999))),
        }
        columns.append(col)

    # Wrap in a component structure
    component = {
        "ref_id": "Package\\Task\\Component",
        "name": "Some Component",
        "component_class_id": "Microsoft.OLEDBSource",
        "classification": "source",
        "outputs": [
            {
                "ref_id": "Package\\Task\\Component.Outputs[Output]",
                "name": "Output",
                "is_error_out": False,
                "output_columns": columns,
            }
        ],
    }

    return component, columns


# --- Property 9: Sensitive Data Redaction Completeness ---
# Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness


class TestPropertySensitiveDataRedactionCompleteness:
    """Property 9: Sensitive Data Redaction Completeness.

    For any element with Sensitive="1" (including SSIS:Sensitive and DTS:Sensitive
    variants) and for any field whose name matches the sensitive patterns (Password,
    pwd, OraPassword, or connection string keys containing "password"/"pwd"), the
    parser SHALL replace the value with "[SENSITIVE - REDACTED]" and set
    "sensitive": true, and the redaction_summary.total_redacted count SHALL equal
    the total number of values actually redacted.

    **Validates: Requirements 13.1, 13.2, 13.4**
    """

    @given(entry=sensitive_marked_dict())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_pre_marked_sensitive_values_are_redacted(self, entry):
        """Values pre-marked with sensitive=true have their value replaced.

        # Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness
        """
        data = {"some_field": entry}
        redacted, count = redact(data)

        assert redacted["some_field"]["value"] == REDACTION_PLACEHOLDER, (
            f"Pre-marked sensitive value not redacted: {redacted['some_field']}"
        )
        assert redacted["some_field"]["sensitive"] is True
        assert count == 1

    @given(result=dict_with_sensitive_field_names())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_sensitive_field_name_values_are_redacted(self, result):
        """Fields whose names match sensitive patterns have values redacted.

        # Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness
        """
        data, sensitive_keys = result
        redacted, count = redact(data)

        # Every sensitive-named field should be redacted
        for key in sensitive_keys:
            if key in redacted:
                field = redacted[key]
                assert isinstance(field, dict), (
                    f"Sensitive field '{key}' should be a dict after redaction, got {type(field)}"
                )
                assert field["value"] == REDACTION_PLACEHOLDER, (
                    f"Sensitive field '{key}' value not redacted: {field}"
                )
                assert field["sensitive"] is True, (
                    f"Sensitive field '{key}' missing sensitive=true flag"
                )

        # Count should match number of unique sensitive keys present
        actual_sensitive_in_data = sum(
            1 for k in redacted if any(p in k.lower() for p in SENSITIVE_FIELD_PATTERNS)
        )
        assert count == actual_sensitive_in_data, (
            f"Redaction count {count} doesn't match actual sensitive fields "
            f"{actual_sensitive_in_data}"
        )

    @given(result=connection_string_with_password())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_connection_string_password_values_are_redacted(self, result):
        """Connection strings with password/pwd keys have those values redacted.

        # Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness
        """
        conn_str, expected_sensitive_count = result
        data = {"connection_string": conn_str}
        redacted, count = redact(data)

        # Verify the redacted connection string contains placeholders
        redacted_str = redacted["connection_string"]
        parts = redacted_str.split(";")

        actual_redacted = 0
        for part in parts:
            if "=" in part:
                key, _, value = part.partition("=")
                key_lower = key.strip().lower()
                if "password" in key_lower or "pwd" in key_lower:
                    assert value == REDACTION_PLACEHOLDER, (
                        f"Connection string key '{key}' not redacted: {value}"
                    )
                    actual_redacted += 1

        assert count == actual_redacted, (
            f"Redaction count {count} doesn't match actual redacted parts "
            f"{actual_redacted}"
        )
        assert count >= 1, "Expected at least one redaction in connection string"

    @given(result=nested_dict_with_sensitive_values())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_nested_sensitive_values_all_redacted(self, result):
        """Sensitive values at different nesting depths are all redacted.

        # Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness
        """
        data, expected_count = result
        redacted, count = redact(data)

        # Verify the count matches expectations
        assert count == expected_count, (
            f"Expected {expected_count} redactions, got {count}. "
            f"Data: {data}, Redacted: {redacted}"
        )

        # Verify pre-marked field is redacted
        assert redacted["marked_field"]["value"] == REDACTION_PLACEHOLDER
        assert redacted["marked_field"]["sensitive"] is True

    @given(
        num_sensitive=st.integers(min_value=1, max_value=8),
        data=st.data(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_redaction_count_equals_actual_redactions(self, num_sensitive, data):
        """The returned redaction count always equals the total number of values actually redacted.

        # Feature: pydtsx-parser, Property 9: Sensitive Data Redaction Completeness
        """
        # Build a structure with a known number of sensitive fields
        test_data = {}
        for i in range(num_sensitive):
            val = data.draw(credential_value)
            test_data[f"password_{i}"] = val

        # Add some safe fields
        test_data["server_name"] = "some-server"
        test_data["user_name"] = "admin"

        redacted, count = redact(test_data)

        # Count how many values were actually replaced
        actual_redacted = 0
        for key, value in redacted.items():
            if isinstance(value, dict) and value.get("value") == REDACTION_PLACEHOLDER:
                actual_redacted += 1

        assert count == actual_redacted, (
            f"Reported count {count} != actual redacted {actual_redacted}"
        )


# --- Property 10: Schema Column Names Not Redacted ---
# Feature: pydtsx-parser, Property 10: Schema Column Names Not Redacted


class TestPropertySchemaColumnNamesNotRedacted:
    """Property 10: Schema Column Names Not Redacted.

    For any data flow column (inputColumn, outputColumn, externalMetadataColumn)
    whose name or cachedName contains "PASSWORD", "PWD", or similar strings,
    the parser SHALL NOT redact the column name or its metadata, as these
    represent schema metadata rather than stored credentials.

    **Validates: Requirements 13.3**
    """

    @given(col_dict=column_context_dict())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_column_name_fields_not_redacted(self, col_dict):
        """Column name/cached_name fields containing password-like strings are NOT redacted.

        # Feature: pydtsx-parser, Property 10: Schema Column Names Not Redacted
        """
        original_name = col_dict["name"]
        original_cached_name = col_dict["cached_name"]

        data = {"output_columns": [col_dict]}
        redacted, count = redact(data)

        redacted_col = redacted["output_columns"][0]

        # Name fields must be preserved as-is
        assert redacted_col["name"] == original_name, (
            f"Column name was wrongly redacted: '{original_name}' -> '{redacted_col['name']}'"
        )
        assert redacted_col["cached_name"] == original_cached_name, (
            f"Column cached_name was wrongly redacted: "
            f"'{original_cached_name}' -> '{redacted_col['cached_name']}'"
        )

        # No redaction should have occurred
        assert count == 0, f"Expected 0 redactions for column metadata, got {count}"

    @given(result=column_in_list_context())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_column_names_in_component_structure_not_redacted(self, result):
        """Column names within a full component structure are preserved unchanged.

        # Feature: pydtsx-parser, Property 10: Schema Column Names Not Redacted
        """
        component, original_columns = result
        data = {"components": [component]}
        redacted, count = redact(data)

        redacted_columns = redacted["components"][0]["outputs"][0]["output_columns"]

        for i, (original, redacted_col) in enumerate(
            zip(original_columns, redacted_columns)
        ):
            assert redacted_col["name"] == original["name"], (
                f"Column {i} name was wrongly redacted: "
                f"'{original['name']}' -> '{redacted_col['name']}'"
            )
            assert redacted_col["cached_name"] == original["cached_name"], (
                f"Column {i} cached_name was wrongly redacted: "
                f"'{original['cached_name']}' -> '{redacted_col['cached_name']}'"
            )

        # No redactions should have occurred for column metadata
        assert count == 0, (
            f"Expected 0 redactions for column names in component, got {count}"
        )

    @given(col_name=password_like_column_name)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_input_column_cached_name_not_redacted(self, col_name):
        """Input columns with password-like cached names are not redacted.

        # Feature: pydtsx-parser, Property 10: Schema Column Names Not Redacted
        """
        input_col = {
            "ref_id": "Package\\Task\\Component.Inputs[Input].Columns[Col]",
            "cached_name": col_name,
            "cached_data_type": "130",
            "cached_length": "50",
            "cached_precision": "0",
            "cached_scale": "0",
            "cached_codepage": "0",
            "lineage_id": "42",
            "external_metadata_column_id": "100",
        }

        data = {"input_columns": [input_col]}
        redacted, count = redact(data)

        assert redacted["input_columns"][0]["cached_name"] == col_name, (
            f"Input column cached_name was wrongly redacted: "
            f"'{col_name}' -> '{redacted['input_columns'][0]['cached_name']}'"
        )
        assert count == 0

    @given(col_name=password_like_column_name)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_external_metadata_column_name_not_redacted(self, col_name):
        """External metadata columns with password-like names are not redacted.

        # Feature: pydtsx-parser, Property 10: Schema Column Names Not Redacted
        """
        ext_col = {
            "ref_id": "Package\\Task\\Comp.Inputs[Input].ExternalColumns[Col]",
            "name": col_name,
            "data_type": "130",
            "length": "50",
            "precision": "0",
            "scale": "0",
            "code_page": "0",
        }

        data = {"external_metadata_columns": [ext_col]}
        redacted, count = redact(data)

        assert redacted["external_metadata_columns"][0]["name"] == col_name, (
            f"External metadata column name was wrongly redacted: "
            f"'{col_name}' -> '{redacted['external_metadata_columns'][0]['name']}'"
        )
        assert count == 0
