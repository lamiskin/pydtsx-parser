"""Property-based tests for SSIS Parser output envelope validity.

Uses Hypothesis to verify that the envelope builder always produces valid,
correctly structured output regardless of the input data.
"""

import json
import os
import re
import tempfile
from datetime import UTC, datetime

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydtsx_parser.envelope import (
    VALID_FILE_TYPES,
    build_envelope,
    collect_source_file_metadata,
)

# --- Strategies ---

# Strategy for generating arbitrary nested dict content (simulating parsed output)
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=200),
)


def json_values():
    """Strategy that generates JSON-compatible values (nested dicts/lists)."""
    return st.recursive(
        json_primitives,
        lambda children: st.one_of(
            st.lists(children, max_size=5),
            st.dictionaries(
                st.text(
                    alphabet=st.characters(
                        whitelist_categories=("L", "N"),
                        whitelist_characters="_",
                    ),
                    min_size=1,
                    max_size=20,
                ),
                children,
                max_size=5,
            ),
        ),
        max_leaves=20,
    )


# Strategy for generating content dicts
content_strategy = st.dictionaries(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"),
            whitelist_characters="_",
        ),
        min_size=1,
        max_size=30,
    ),
    json_values(),
    max_size=10,
)

# Strategy for valid file types
file_type_strategy = st.sampled_from(sorted(VALID_FILE_TYPES))

# Strategy for redaction counts
redaction_count_strategy = st.integers(min_value=0, max_value=10000)

# Strategy for file content (bytes written to temp files)
file_content_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z"),
    ),
    min_size=0,
    max_size=500,
)

# Strategy for generating text with special characters and Unicode
special_content_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "S", "Z", "M", "C"),
    ),
    min_size=0,
    max_size=1000,
)


# --- Helpers ---

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


def is_snake_case(key: str) -> bool:
    """Check if a key is in snake_case format."""
    return SNAKE_CASE_PATTERN.match(key) is not None


def collect_all_keys(obj, exclude_raw_attributes=True, path=""):
    """Recursively collect all keys from a nested dict structure.

    Excludes keys inside raw_attributes sub-objects per Property 7.
    """
    keys = []
    if isinstance(obj, dict):
        for key in obj:
            current_path = f"{path}.{key}" if path else key
            # Skip keys inside raw_attributes
            if exclude_raw_attributes and key == "raw_attributes":
                continue
            keys.append((current_path, key))
            if isinstance(obj[key], (dict, list)):
                keys.extend(
                    collect_all_keys(obj[key], exclude_raw_attributes, current_path)
                )
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            keys.extend(collect_all_keys(item, exclude_raw_attributes, f"{path}[{i}]"))
    return keys


# --- Property 7: Output Envelope Validity ---
# Feature: pydtsx-parser, Property 7: Output Envelope Validity


class TestPropertyOutputEnvelopeValidity:
    """Property 7: Output Envelope Validity.

    For any successfully parsed SSIS file, the output SHALL be valid JSON
    containing exactly the required top-level fields (format_version as
    semantic version string, parser_version as semantic version string,
    source_file_path as absolute path, file_type as one of the four allowed
    values, parsed_at as ISO 8601 timestamp, source_file_metadata as an
    object), and all keys in the output (excluding raw_attributes sub-objects)
    SHALL be in snake_case format.

    **Validates: Requirements 6.1, 6.2**
    """

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_envelope_contains_required_top_level_fields(
        self, content, file_type, redaction_count
    ):
        """The envelope always contains all required top-level fields."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)

            # Required top-level fields per Requirement 6.1
            assert "format_version" in result
            assert "parser_version" in result
            assert "source_file_path" in result
            assert "file_type" in result
            assert "parsed_at" in result
            assert "source_file_metadata" in result
        finally:
            os.unlink(temp_path)

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_format_version_is_semantic_version(
        self, content, file_type, redaction_count
    ):
        """format_version is always a semantic version string."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)
            assert SEMVER_PATTERN.match(result["format_version"])
        finally:
            os.unlink(temp_path)

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_parser_version_is_semantic_version(
        self, content, file_type, redaction_count
    ):
        """parser_version is always a semantic version string."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)
            assert SEMVER_PATTERN.match(result["parser_version"])
        finally:
            os.unlink(temp_path)

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_source_file_path_is_absolute(self, content, file_type, redaction_count):
        """source_file_path is always an absolute path."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)
            assert os.path.isabs(result["source_file_path"])
        finally:
            os.unlink(temp_path)

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_file_type_is_valid_value(self, content, file_type, redaction_count):
        """file_type is always one of the four allowed values."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)
            assert result["file_type"] in VALID_FILE_TYPES
        finally:
            os.unlink(temp_path)

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_parsed_at_is_iso8601_timestamp(self, content, file_type, redaction_count):
        """parsed_at is always a valid ISO 8601 timestamp with timezone."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)
            dt = datetime.fromisoformat(result["parsed_at"])
            assert dt.tzinfo is not None
        finally:
            os.unlink(temp_path)

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_source_file_metadata_is_object(self, content, file_type, redaction_count):
        """source_file_metadata is always a dict/object."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)
            assert isinstance(result["source_file_metadata"], dict)
        finally:
            os.unlink(temp_path)

    @given(
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100)
    def test_all_envelope_keys_are_snake_case(self, file_type, redaction_count):
        """All keys in the envelope (excluding raw_attributes) are snake_case."""
        # Feature: pydtsx-parser, Property 7: Output Envelope Validity
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            # Use a simple content dict with snake_case keys
            content = {"test_key": "value", "nested_data": {"inner_key": 42}}
            result = build_envelope(content, temp_path, file_type, redaction_count)

            # Collect all keys (excluding those inside raw_attributes)
            all_keys = collect_all_keys(result, exclude_raw_attributes=True)

            # The envelope's own keys must be snake_case.
            # We check keys that are part of the envelope structure (not
            # user-provided content keys or data_type_map numeric keys).
            envelope_keys = [
                (path, key)
                for path, key in all_keys
                if not path.startswith("content.")
                and not path.startswith("data_type_map.")
            ]

            for path, key in envelope_keys:
                # data_type_map has numeric keys like "2", "3" etc.
                if key.isdigit():
                    continue
                assert is_snake_case(key), (
                    f"Key '{key}' at path '{path}' is not snake_case"
                )
        finally:
            os.unlink(temp_path)


# --- Property 8: JSON Output Always Valid ---
# Feature: pydtsx-parser, Property 8: JSON Output Always Valid


class TestPropertyJsonOutputAlwaysValid:
    """Property 8: JSON Output Always Valid.

    For any input file (including files with special characters, Unicode
    content, very long strings, or unusual XML constructs), the parser SHALL
    produce output that is valid JSON parseable by a standard JSON parser.

    **Validates: Requirements 6.5**
    """

    @given(
        content=content_strategy,
        file_type=file_type_strategy,
        redaction_count=redaction_count_strategy,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_envelope_always_produces_valid_json(
        self, content, file_type, redaction_count
    ):
        """build_envelope output is always valid JSON for any content dict."""
        # Feature: pydtsx-parser, Property 8: JSON Output Always Valid
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            result = build_envelope(content, temp_path, file_type, redaction_count)

            # Must serialize without error
            json_str = json.dumps(result)
            # Must parse back without error
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)
        finally:
            os.unlink(temp_path)

    @given(content_text=special_content_strategy)
    @settings(max_examples=100)
    def test_envelope_valid_json_with_special_characters_in_content(self, content_text):
        """Envelope produces valid JSON even with special/Unicode content."""
        # Feature: pydtsx-parser, Property 8: JSON Output Always Valid
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            # Embed special characters in content values
            content = {
                "special_text": content_text,
                "nested": {"unicode_value": content_text},
                "list_values": [content_text, content_text],
            }
            result = build_envelope(content, temp_path, "dtsx_package", 0)

            # Must serialize and parse back
            json_str = json.dumps(result, ensure_ascii=False)
            parsed = json.loads(json_str)
            assert parsed["content"]["special_text"] == content_text
        finally:
            os.unlink(temp_path)

    @given(
        length=st.integers(min_value=0, max_value=5000),
        file_type=file_type_strategy,
    )
    @settings(max_examples=100)
    def test_envelope_valid_json_with_long_strings(self, length, file_type):
        """Envelope produces valid JSON even with very long string values."""
        # Feature: pydtsx-parser, Property 8: JSON Output Always Valid
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            f.write("<root>test</root>")
            temp_path = f.name

        try:
            long_string = "a" * length
            content = {"long_value": long_string}
            result = build_envelope(content, temp_path, file_type, 0)

            json_str = json.dumps(result)
            parsed = json.loads(json_str)
            assert parsed["content"]["long_value"] == long_string
        finally:
            os.unlink(temp_path)


# --- Property 18: Source File Metadata Accuracy ---
# Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy


class TestPropertySourceFileMetadataAccuracy:
    """Property 18: Source File Metadata Accuracy.

    For any successfully parsed SSIS file, the output's source_file_metadata
    object SHALL contain: file_name matching the basename of the source file,
    file_size_bytes matching the actual file size, last_modified as an ISO 8601
    timestamp, created as an ISO 8601 timestamp, and owner matching the
    filesystem owner (or null if unavailable).

    **Validates: Requirements 6.6, 6.7**
    """

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_file_name_matches_basename(self, file_content):
        """file_name always matches the basename of the source file."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            meta = collect_source_file_metadata(temp_path)
            expected_name = os.path.basename(temp_path)
            assert meta["file_name"] == expected_name
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_file_size_bytes_matches_actual_size(self, file_content):
        """file_size_bytes always matches the actual filesystem file size."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            actual_size = os.path.getsize(temp_path)
            meta = collect_source_file_metadata(temp_path)
            assert meta["file_size_bytes"] == actual_size
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_last_modified_is_iso8601_timestamp(self, file_content):
        """last_modified is always a valid ISO 8601 timestamp with timezone."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            meta = collect_source_file_metadata(temp_path)
            dt = datetime.fromisoformat(meta["last_modified"])
            assert dt.tzinfo is not None
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_last_modified_matches_filesystem_mtime(self, file_content):
        """last_modified timestamp matches the file's actual mtime."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            stat_result = os.stat(temp_path)
            expected_dt = datetime.fromtimestamp(stat_result.st_mtime, tz=UTC)
            meta = collect_source_file_metadata(temp_path)
            actual_dt = datetime.fromisoformat(meta["last_modified"])
            # Compare as UTC timestamps (allow 1 second tolerance for rounding)
            diff = abs(
                (actual_dt - expected_dt.astimezone(actual_dt.tzinfo)).total_seconds()
            )
            assert diff < 1.0
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_created_is_iso8601_timestamp(self, file_content):
        """created is always a valid ISO 8601 timestamp with timezone."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            meta = collect_source_file_metadata(temp_path)
            dt = datetime.fromisoformat(meta["created"])
            assert dt.tzinfo is not None
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_created_matches_filesystem_ctime(self, file_content):
        """created timestamp matches the file's actual ctime."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            stat_result = os.stat(temp_path)
            expected_dt = datetime.fromtimestamp(stat_result.st_ctime, tz=UTC)
            meta = collect_source_file_metadata(temp_path)
            actual_dt = datetime.fromisoformat(meta["created"])
            # Compare as UTC timestamps (allow 1 second tolerance for rounding)
            diff = abs(
                (actual_dt - expected_dt.astimezone(actual_dt.tzinfo)).total_seconds()
            )
            assert diff < 1.0
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_owner_is_string_or_null(self, file_content):
        """owner is always a string or null (never raises)."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            meta = collect_source_file_metadata(temp_path)
            assert meta["owner"] is None or isinstance(meta["owner"], str)
        finally:
            os.unlink(temp_path)

    @given(file_content=file_content_strategy)
    @settings(max_examples=100)
    def test_metadata_contains_all_required_fields(self, file_content):
        """source_file_metadata always contains all five required fields."""
        # Feature: pydtsx-parser, Property 18: Source File Metadata Accuracy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".dtsx", delete=False, encoding="utf-8"
        ) as f:
            f.write(file_content)
            temp_path = f.name

        try:
            meta = collect_source_file_metadata(temp_path)
            required_keys = {
                "file_name",
                "file_size_bytes",
                "last_modified",
                "created",
                "owner",
            }
            assert required_keys == set(meta.keys())
        finally:
            os.unlink(temp_path)
