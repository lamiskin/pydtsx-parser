"""Unit tests for the CLI module.

Tests cover: single file parsing to stdout, directory parsing, --output flag,
--pretty flag, unsupported file type warning, non-existent path error, and
empty directory output.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

from pydtsx_parser.cli import main, parse_args

# -- Minimal valid SSIS XML fixtures --

MINIMAL_DTSX = (
    '<?xml version="1.0"?>\n'
    '<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
    'DTS:refId="Package" DTS:CreationName="Microsoft.Package" '
    'DTS:ObjectName="TestPackage" DTS:DTSID="{TEST-GUID}">'
    "</DTS:Executable>"
)

MINIMAL_PARAMS = (
    '<?xml version="1.0"?>\n'
    '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">'
    "</SSIS:Parameters>"
)


class TestParseArgs:
    """Tests for parse_args function."""

    def test_positional_path(self):
        ns = parse_args(["some/path"])
        assert ns.path == "some/path"
        assert ns.output is None
        assert ns.pretty is False

    def test_output_flag_short(self):
        ns = parse_args(["file.dtsx", "-o", "out.json"])
        assert ns.output == "out.json"

    def test_output_flag_long(self):
        ns = parse_args(["file.dtsx", "--output", "out.json"])
        assert ns.output == "out.json"

    def test_pretty_flag_short(self):
        ns = parse_args(["file.dtsx", "-p"])
        assert ns.pretty is True

    def test_pretty_flag_long(self):
        ns = parse_args(["file.dtsx", "--pretty"])
        assert ns.pretty is True

    def test_all_flags_combined(self):
        ns = parse_args(["dir/", "-o", "out.json", "-p"])
        assert ns.path == "dir/"
        assert ns.output == "out.json"
        assert ns.pretty is True


class TestMainSingleFile:
    """Tests for main() with a single file (Req 12.1)."""

    def test_single_file_to_stdout(self, tmp_path, capsys):
        """Parsing a valid .dtsx outputs valid JSON to stdout."""
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        exit_code = main([str(dtsx_file)])

        assert exit_code == 0
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["format_version"] == "1.0.0"
        assert result["file_type"] == "dtsx_package"
        assert "content" in result

    def test_single_file_returns_zero(self, tmp_path, capsys):
        """Successful parse returns exit code 0."""
        dtsx_file = tmp_path / "test.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        exit_code = main([str(dtsx_file)])

        assert exit_code == 0


class TestMainArgsFromSysArgv:
    """main(args=None) falls back to sys.argv[1:]."""

    def test_none_args_uses_sys_argv(self, tmp_path, capsys):
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        with patch.object(sys, "argv", ["pydtsx-parser", str(dtsx_file)]):
            exit_code = main()

        assert exit_code == 0
        result = json.loads(capsys.readouterr().out)
        assert result["file_type"] == "dtsx_package"


class TestMainDispatchErrors:
    """Errors raised by dispatch() itself, for a single file."""

    def test_malformed_xml_returns_error(self, tmp_path, capsys):
        bad_file = tmp_path / "bad.dtsx"
        bad_file.write_text("not xml at all!!", encoding="utf-8")

        exit_code = main([str(bad_file)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Error:" in captured.err

    def test_unexpected_exception_returns_error(self, tmp_path, capsys):
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        with patch("pydtsx_parser.cli.dispatch", side_effect=RuntimeError("boom")):
            exit_code = main([str(dtsx_file)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.err
        assert "boom" in captured.err


class TestMainOutputWriteFailure:
    """--output when the write itself fails (permissions, disk, etc.)."""

    def test_oserror_writing_output_returns_error(self, tmp_path, capsys):
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")
        output_file = tmp_path / "output.json"

        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            exit_code = main([str(dtsx_file), "--output", str(output_file)])

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Cannot write to output file" in captured.err


class TestMainDirectory:
    """Tests for main() with a directory (Req 12.2)."""

    def test_directory_produces_combined_output(self, tmp_path, capsys):
        """Directory parsing produces combined project-level JSON output."""
        (tmp_path / "Package.dtsx").write_text(MINIMAL_DTSX, encoding="utf-8")
        (tmp_path / "Project.params").write_text(MINIMAL_PARAMS, encoding="utf-8")

        exit_code = main([str(tmp_path)])

        assert exit_code == 0
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["file_type"] == "project_directory"
        assert result["summary"]["total_files"] == 2
        assert result["summary"]["packages"] == 1
        assert result["summary"]["parameters"] == 1

    def test_directory_includes_packages_and_params(self, tmp_path, capsys):
        """Combined output contains packages and parameters arrays."""
        (tmp_path / "test.dtsx").write_text(MINIMAL_DTSX, encoding="utf-8")
        (tmp_path / "Project.params").write_text(MINIMAL_PARAMS, encoding="utf-8")

        main([str(tmp_path)])

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert len(result["packages"]) == 1
        assert len(result["parameters"]) == 1


class TestMainOutputFlag:
    """Tests for --output flag (Req 12.3)."""

    def test_output_writes_to_file(self, tmp_path, capsys):
        """--output flag writes JSON to the specified file."""
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")
        output_file = tmp_path / "output.json"

        exit_code = main([str(dtsx_file), "--output", str(output_file)])

        assert exit_code == 0
        # stdout should be empty (output went to file)
        captured = capsys.readouterr()
        assert captured.out == ""
        # File should contain valid JSON
        content = output_file.read_text(encoding="utf-8")
        result = json.loads(content)
        assert result["file_type"] == "dtsx_package"

    def test_output_creates_parent_directories(self, tmp_path, capsys):
        """--output creates parent directories if they don't exist."""
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")
        output_file = tmp_path / "nested" / "dir" / "output.json"

        exit_code = main([str(dtsx_file), "-o", str(output_file)])

        assert exit_code == 0
        assert output_file.exists()
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result["format_version"] == "1.0.0"


class TestMainPrettyFlag:
    """Tests for --pretty flag (Req 12.4)."""

    def test_pretty_produces_indented_json(self, tmp_path, capsys):
        """--pretty flag produces JSON with 2-space indentation."""
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        exit_code = main([str(dtsx_file), "--pretty"])

        assert exit_code == 0
        captured = capsys.readouterr()
        # Pretty-printed JSON should have newlines and 2-space indent
        lines = captured.out.split("\n")
        # The first line should be the opening brace
        assert lines[0].strip() == "{"
        # Indented lines should use 2 spaces
        indented_lines = [l for l in lines if l.startswith("  ")]
        assert len(indented_lines) > 0
        # Verify it's valid JSON
        result = json.loads(captured.out)
        assert "format_version" in result

    def test_pretty_uses_two_space_indent(self, tmp_path, capsys):
        """Pretty output uses exactly 2-space indent, not tabs or 4-space."""
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        main([str(dtsx_file), "-p"])

        captured = capsys.readouterr()
        # Re-serialize with indent=2 and compare
        result = json.loads(captured.out)
        expected = json.dumps(result, indent=2, ensure_ascii=False)
        assert captured.out.strip() == expected.strip()

    def test_without_pretty_is_compact(self, tmp_path, capsys):
        """Without --pretty, output is compact (single line)."""
        dtsx_file = tmp_path / "Package.dtsx"
        dtsx_file.write_text(MINIMAL_DTSX, encoding="utf-8")

        main([str(dtsx_file)])

        captured = capsys.readouterr()
        # Compact JSON should be on a single line (no pretty-print newlines)
        # Note: the print() adds a trailing newline
        output_lines = captured.out.strip().split("\n")
        assert len(output_lines) == 1


class TestMainUnsupportedFileType:
    """Tests for unsupported file type handling (Req 12.5)."""

    def test_unsupported_file_returns_zero(self, tmp_path, capsys):
        """Unsupported file type returns exit code 0 (not an error)."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("hello world", encoding="utf-8")

        exit_code = main([str(txt_file)])

        assert exit_code == 0

    def test_unsupported_file_warns_to_stderr(self, tmp_path, caplog):
        """Unsupported file type logs a warning to stderr."""
        import logging

        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("hello world", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            main([str(txt_file)])

        assert any("unsupported" in r.message.lower() for r in caplog.records)


class TestMainNonExistentPath:
    """Tests for non-existent path handling (Req 12.6)."""

    def test_nonexistent_path_returns_nonzero(self, capsys):
        """Non-existent path returns non-zero exit code."""
        exit_code = main(["nonexistent/path/to/file.dtsx"])

        assert exit_code != 0

    def test_nonexistent_path_errors_to_stderr(self, capsys):
        """Non-existent path prints error message to stderr."""
        main(["nonexistent/path/to/file.dtsx"])

        captured = capsys.readouterr()
        assert "error" in captured.err.lower() or "Error" in captured.err
        assert captured.out == ""


class TestMainEmptyDirectory:
    """Tests for empty directory handling (Req 12.7)."""

    def test_empty_directory_returns_zero(self, tmp_path, capsys):
        """Empty directory returns exit code 0 (valid empty output)."""
        exit_code = main([str(tmp_path)])

        assert exit_code == 0

    def test_empty_directory_produces_empty_project_structure(self, tmp_path, capsys):
        """Empty directory produces valid JSON with empty collections."""
        main([str(tmp_path)])

        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["file_type"] == "project_directory"
        assert result["summary"]["total_files"] == 0
        assert result["packages"] == []
        assert result["connection_managers"] == []
        assert result["parameters"] == []
        assert result["projects"] == []
