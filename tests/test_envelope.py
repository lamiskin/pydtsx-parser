"""Unit tests for pydtsx_parser.envelope module."""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

from pydtsx_parser.envelope import (
    FORMAT_VERSION,
    PARSER_VERSION,
    VALID_FILE_TYPES,
    build_envelope,
    collect_source_file_metadata,
)


@pytest.fixture
def temp_file():
    """Create a temporary file for testing metadata collection."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
        f.write("<DTS:Executable>test</DTS:Executable>")
        f.flush()
        yield f.name
    os.unlink(f.name)


class TestBuildEnvelope:
    """Tests for build_envelope()."""

    def test_contains_format_version(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        assert result["format_version"] == "1.0.0"

    def test_contains_parser_version(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        assert result["parser_version"] == PARSER_VERSION

    def test_source_file_path_is_absolute(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        assert os.path.isabs(result["source_file_path"])

    def test_file_type_preserved(self, temp_file):
        for file_type in VALID_FILE_TYPES:
            result = build_envelope({}, temp_file, file_type, 0)
            assert result["file_type"] == file_type

    def test_parsed_at_is_iso8601_with_timezone(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        parsed_at = result["parsed_at"]
        # Should parse without error and have timezone info
        dt = datetime.fromisoformat(parsed_at)
        assert dt.tzinfo is not None

    def test_contains_data_type_map(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        assert "data_type_map" in result
        assert result["data_type_map"]["130"] == "wstr"
        assert result["data_type_map"]["3"] == "i4"

    def test_redaction_summary(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 5)
        assert result["redaction_summary"] == {"total_redacted": 5}

    def test_content_is_wrapped(self, temp_file):
        content = {"executables": [], "variables": []}
        result = build_envelope(content, temp_file, "dtsx_package", 0)
        assert result["content"] == content

    def test_source_file_metadata_present(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        assert "source_file_metadata" in result
        meta = result["source_file_metadata"]
        assert "file_name" in meta
        assert "file_size_bytes" in meta
        assert "last_modified" in meta
        assert "created" in meta
        assert "owner" in meta

    def test_output_is_valid_json(self, temp_file):
        content = {"key": "value", "nested": {"list": [1, 2, 3]}}
        result = build_envelope(content, temp_file, "dtsx_package", 2)
        # Should serialize to valid JSON without error
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed["format_version"] == "1.0.0"

    def test_all_required_top_level_keys(self, temp_file):
        result = build_envelope({}, temp_file, "dtsx_package", 0)
        required_keys = {
            "format_version",
            "parser_version",
            "source_file_path",
            "file_type",
            "parsed_at",
            "source_file_metadata",
            "data_type_map",
            "redaction_summary",
            "content",
        }
        assert required_keys.issubset(set(result.keys()))


class TestCollectSourceFileMetadata:
    """Tests for collect_source_file_metadata()."""

    def test_file_name_is_basename(self, temp_file):
        meta = collect_source_file_metadata(temp_file)
        assert meta["file_name"] == os.path.basename(temp_file)

    def test_file_size_bytes_matches(self, temp_file):
        meta = collect_source_file_metadata(temp_file)
        expected_size = os.path.getsize(temp_file)
        assert meta["file_size_bytes"] == expected_size

    def test_last_modified_is_iso8601(self, temp_file):
        meta = collect_source_file_metadata(temp_file)
        dt = datetime.fromisoformat(meta["last_modified"])
        assert dt.tzinfo is not None

    def test_created_is_iso8601(self, temp_file):
        meta = collect_source_file_metadata(temp_file)
        dt = datetime.fromisoformat(meta["created"])
        assert dt.tzinfo is not None

    def test_owner_is_string_or_none(self, temp_file):
        meta = collect_source_file_metadata(temp_file)
        assert meta["owner"] is None or isinstance(meta["owner"], str)

    def test_owner_null_fallback_on_failure(self, temp_file):
        """Owner should be null when resolution fails."""
        with patch("pydtsx_parser.envelope._resolve_file_owner", return_value=None):
            meta = collect_source_file_metadata(temp_file)
            assert meta["owner"] is None

    def test_file_size_correct_for_known_content(self):
        """File size should match actual written bytes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsx", delete=False) as f:
            content = "x" * 100
            f.write(content)
            f.flush()
            temp_path = f.name
        try:
            meta = collect_source_file_metadata(temp_path)
            assert meta["file_size_bytes"] == 100
        finally:
            os.unlink(temp_path)


class TestConstants:
    """Tests for module-level constants."""

    def test_format_version_is_semver(self):
        parts = FORMAT_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_parser_version_is_semver(self):
        parts = PARSER_VERSION.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_valid_file_types(self):
        assert "dtsx_package" in VALID_FILE_TYPES
        assert "dtproj_project" in VALID_FILE_TYPES
        assert "conmgr_connection" in VALID_FILE_TYPES
        assert "params_parameters" in VALID_FILE_TYPES
