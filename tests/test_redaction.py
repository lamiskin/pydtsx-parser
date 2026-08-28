"""Unit tests for the redaction module."""

from pydtsx_parser.redaction import (
    REDACTION_PLACEHOLDER,
    is_sensitive_attribute,
    is_sensitive_field,
    redact,
)


class TestIsSensitiveField:
    """Tests for is_sensitive_field helper."""

    def test_password_match(self):
        assert is_sensitive_field("password") is True

    def test_password_case_insensitive(self):
        assert is_sensitive_field("Password") is True
        assert is_sensitive_field("PASSWORD") is True

    def test_pwd_match(self):
        assert is_sensitive_field("pwd") is True
        assert is_sensitive_field("Pwd") is True

    def test_orapassword_match(self):
        assert is_sensitive_field("orapassword") is True
        assert is_sensitive_field("OraPassword") is True

    def test_password_substring_match(self):
        """Fields containing 'password' anywhere should match."""
        assert is_sensitive_field("user_password") is True
        assert is_sensitive_field("db_password_field") is True

    def test_non_sensitive_field(self):
        assert is_sensitive_field("username") is False
        assert is_sensitive_field("server_name") is False
        assert is_sensitive_field("connection_string") is False

    def test_empty_field(self):
        assert is_sensitive_field("") is False


class TestIsSensitiveAttribute:
    """Tests for is_sensitive_attribute helper."""

    def test_sensitive_equals_1(self):
        assert is_sensitive_attribute({"Sensitive": "1"}) is True

    def test_dts_sensitive(self):
        assert is_sensitive_attribute({"DTS:Sensitive": "1"}) is True

    def test_ssis_sensitive(self):
        assert is_sensitive_attribute({"SSIS:Sensitive": "1"}) is True

    def test_sensitive_equals_0(self):
        assert is_sensitive_attribute({"Sensitive": "0"}) is False

    def test_no_sensitive_key(self):
        assert is_sensitive_attribute({"name": "test"}) is False

    def test_empty_dict(self):
        assert is_sensitive_attribute({}) is False


class TestRedact:
    """Tests for the main redact() function."""

    def test_empty_dict(self):
        data = {}
        result, count = redact(data)
        assert result == {}
        assert count == 0

    def test_no_sensitive_data(self):
        data = {
            "name": "MyPackage",
            "version": "1.0",
            "executables": [{"name": "Task1"}],
        }
        result, count = redact(data)
        assert result == data
        assert count == 0

    def test_redact_already_marked_sensitive(self):
        """Elements already marked sensitive by extractors should be redacted."""
        data = {
            "connection_managers": [
                {
                    "object_name": "DB",
                    "properties": {
                        "password": {"value": "secret123", "sensitive": True},
                    },
                }
            ]
        }
        result, count = redact(data)
        assert (
            result["connection_managers"][0]["properties"]["password"]["value"]
            == REDACTION_PLACEHOLDER
        )
        assert (
            result["connection_managers"][0]["properties"]["password"]["sensitive"]
            is True
        )
        assert count == 1

    def test_redact_sensitive_field_by_name(self):
        """Fields named 'password' should be redacted."""
        data = {
            "properties": {
                "password": "mysecret",
                "server_name": "myserver",
            }
        }
        result, count = redact(data)
        assert result["properties"]["password"] == {
            "value": REDACTION_PLACEHOLDER,
            "sensitive": True,
        }
        assert result["properties"]["server_name"] == "myserver"
        assert count == 1

    def test_redact_pwd_field(self):
        """Fields named 'pwd' should be redacted."""
        data = {"config": {"pwd": "topsecret"}}
        result, count = redact(data)
        assert result["config"]["pwd"] == {
            "value": REDACTION_PLACEHOLDER,
            "sensitive": True,
        }
        assert count == 1

    def test_redact_orapassword_field(self):
        """Fields named 'orapassword' should be redacted."""
        data = {"oracle": {"orapassword": "oracle_secret"}}
        result, count = redact(data)
        assert result["oracle"]["orapassword"] == {
            "value": REDACTION_PLACEHOLDER,
            "sensitive": True,
        }
        assert count == 1

    def test_redact_connection_string_with_password(self):
        """Connection strings containing Password= should be redacted."""
        data = {
            "properties": {
                "connection_string": (
                    "Data Source=myserver;"
                    "Initial Catalog=mydb;"
                    "Password=secret123;"
                    "User ID=admin"
                ),
            }
        }
        result, count = redact(data)
        conn_str = result["properties"]["connection_string"]
        assert "secret123" not in conn_str
        assert REDACTION_PLACEHOLDER in conn_str
        assert "Data Source=myserver" in conn_str
        assert "User ID=admin" in conn_str
        assert count == 1

    def test_redact_connection_string_with_pwd(self):
        """Connection strings containing pwd= should be redacted."""
        data = {
            "properties": {
                "connection_string": "Server=myserver;pwd=secret;User=admin",
            }
        }
        result, count = redact(data)
        conn_str = result["properties"]["connection_string"]
        assert "secret" not in conn_str
        assert REDACTION_PLACEHOLDER in conn_str
        assert count == 1

    def test_no_redact_column_name_password(self):
        """Column names containing 'PASSWORD' should NOT be redacted."""
        data = {
            "components": [
                {
                    "outputs": [
                        {
                            "output_columns": [
                                {
                                    "ref_id": "col1",
                                    "name": "USER_PASSWORD",
                                    "data_type": "130",
                                    "length": "50",
                                    "precision": "0",
                                    "scale": "0",
                                    "code_page": "0",
                                    "lineage_id": "42",
                                    "error_row_disposition": "FailComponent",
                                    "truncation_row_disposition": "FailComponent",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        result, count = redact(data)
        col = result["components"][0]["outputs"][0]["output_columns"][0]
        assert col["name"] == "USER_PASSWORD"
        assert count == 0

    def test_no_redact_cached_name_with_pwd(self):
        """Input column cachedName containing 'PWD' should NOT be redacted."""
        data = {
            "components": [
                {
                    "inputs": [
                        {
                            "input_columns": [
                                {
                                    "ref_id": "col1",
                                    "cached_name": "SPASSWORD",
                                    "cached_data_type": "130",
                                    "cached_length": "100",
                                    "cached_precision": "0",
                                    "cached_scale": "0",
                                    "cached_codepage": "0",
                                    "lineage_id": "55",
                                    "external_metadata_column_id": "101",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        result, count = redact(data)
        col = result["components"][0]["inputs"][0]["input_columns"][0]
        assert col["cached_name"] == "SPASSWORD"
        assert count == 0

    def test_does_not_modify_original(self):
        """redact() should not modify the original dict."""
        data = {"properties": {"password": "secret"}}
        _, _ = redact(data)
        assert data["properties"]["password"] == "secret"

    def test_multiple_redactions_counted(self):
        """Multiple sensitive fields are all counted."""
        data = {
            "conn1": {"password": "s1"},
            "conn2": {"pwd": "s2"},
            "conn3": {"orapassword": "s3"},
        }
        result, count = redact(data)
        assert count == 3

    def test_nested_deep_redaction(self):
        """Deeply nested sensitive fields are found and redacted."""
        data = {
            "level1": {"level2": {"level3": {"level4": {"password": "deep_secret"}}}}
        }
        result, count = redact(data)
        assert result["level1"]["level2"]["level3"]["level4"]["password"] == {
            "value": REDACTION_PLACEHOLDER,
            "sensitive": True,
        }
        assert count == 1

    def test_already_redacted_not_double_counted(self):
        """Values already set to REDACTION_PLACEHOLDER should not be counted again."""
        data = {
            "properties": {
                "password": {"value": REDACTION_PLACEHOLDER, "sensitive": True}
            }
        }
        result, count = redact(data)
        assert count == 0

    def test_redact_returns_correct_count_with_connection_string_and_fields(self):
        """Combined field-name and connection-string redactions are summed."""
        data = {
            "password": "direct_secret",
            "connection_string": "Server=x;Password=y;User=z",
        }
        result, count = redact(data)
        assert count == 2

    def test_no_redact_column_name_in_derived_columns(self):
        """Derived column names containing PASSWORD should not be redacted."""
        data = {
            "derived_columns": [
                {
                    "column_name": "PASSWORD_HASH",
                    "expression": "HASHBYTES(col)",
                    "data_type": "130",
                    "length": "64",
                    "precision": "0",
                    "scale": "0",
                    "code_page": "0",
                    "is_overwrite": False,
                    "lineage_id": "99",
                }
            ]
        }
        result, count = redact(data)
        assert result["derived_columns"][0]["column_name"] == "PASSWORD_HASH"
        assert count == 0
