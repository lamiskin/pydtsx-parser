"""Unit tests for the Project.params file parser."""

import os
import tempfile

import pytest

from pydtsx_parser.errors import FileNotFoundError, MalformedXMLError
from pydtsx_parser.parsers.params import parse_params


def _write_temp_params(xml_content: str) -> str:
    """Write XML content to a temporary .params file and return the path."""
    fd, path = tempfile.mkstemp(suffix=".params")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(xml_content)
    return path


@pytest.fixture
def empty_params_self_closing():
    """Project.params with self-closing root element (no parameters)."""
    content = (
        '<?xml version="1.0"?>\n'
        '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS" />'
    )
    path = _write_temp_params(content)
    yield path
    os.unlink(path)


@pytest.fixture
def empty_params_open_close():
    """Project.params with empty open/close root element (no parameters)."""
    content = (
        '<?xml version="1.0"?>\n'
        '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">\n'
        "</SSIS:Parameters>"
    )
    path = _write_temp_params(content)
    yield path
    os.unlink(path)


@pytest.fixture
def single_param_file():
    """Project.params with one parameter defined."""
    content = (
        '<?xml version="1.0"?>\n'
        '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">\n'
        '  <SSIS:Parameter SSIS:Name="ServerName">\n'
        "    <SSIS:Properties>\n"
        '      <SSIS:Property SSIS:Name="DataType">18</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Value">localhost</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Sensitive">0</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Required">1</SSIS:Property>\n'
        "    </SSIS:Properties>\n"
        "  </SSIS:Parameter>\n"
        "</SSIS:Parameters>"
    )
    path = _write_temp_params(content)
    yield path
    os.unlink(path)


@pytest.fixture
def multi_param_file():
    """Project.params with multiple parameters including a sensitive one."""
    content = (
        '<?xml version="1.0"?>\n'
        '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">\n'
        '  <SSIS:Parameter SSIS:Name="ServerName">\n'
        "    <SSIS:Properties>\n"
        '      <SSIS:Property SSIS:Name="DataType">18</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Value">prod-server.example.com</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Sensitive">0</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Required">1</SSIS:Property>\n'
        "    </SSIS:Properties>\n"
        "  </SSIS:Parameter>\n"
        '  <SSIS:Parameter SSIS:Name="DbPassword">\n'
        "    <SSIS:Properties>\n"
        '      <SSIS:Property SSIS:Name="DataType">18</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Value"></SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Sensitive">1</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Required">1</SSIS:Property>\n'
        "    </SSIS:Properties>\n"
        "  </SSIS:Parameter>\n"
        '  <SSIS:Parameter SSIS:Name="BatchSize">\n'
        "    <SSIS:Properties>\n"
        '      <SSIS:Property SSIS:Name="DataType">3</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Value">1000</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Sensitive">0</SSIS:Property>\n'
        '      <SSIS:Property SSIS:Name="Required">0</SSIS:Property>\n'
        "    </SSIS:Properties>\n"
        "  </SSIS:Parameter>\n"
        "</SSIS:Parameters>"
    )
    path = _write_temp_params(content)
    yield path
    os.unlink(path)


class TestParseParamsErrorHandling:
    """Tests for error conditions in parse_params."""

    def test_null_file_path_raises_file_not_found(self):
        """Empty string path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_params("")

    def test_none_file_path_raises_file_not_found(self):
        """None path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_params(None)

    def test_nonexistent_path_raises_file_not_found(self):
        """Non-existent path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_params("/nonexistent/path/Project.params")

    def test_malformed_xml_raises_malformed_xml_error(self):
        """Malformed XML raises MalformedXMLError with file path and reason."""
        path = _write_temp_params("<broken><unclosed")
        try:
            with pytest.raises(MalformedXMLError) as exc_info:
                parse_params(path)
            assert path in str(exc_info.value)
        finally:
            os.unlink(path)

    def test_malformed_xml_error_includes_details(self):
        """MalformedXMLError includes parse failure reason."""
        path = _write_temp_params("not xml at all &&&")
        try:
            with pytest.raises(MalformedXMLError) as exc_info:
                parse_params(path)
            assert "Malformed XML" in exc_info.value.reason
        finally:
            os.unlink(path)


class TestParseParamsEmptyParameters:
    """Tests for empty parameter handling (Requirement 5.2)."""

    def test_self_closing_root_returns_empty_list(self, empty_params_self_closing):
        """Self-closing SSIS:Parameters returns empty parameters list."""
        result = parse_params(empty_params_self_closing)
        assert result["parameters"] == []

    def test_open_close_root_returns_empty_list(self, empty_params_open_close):
        """Empty open/close SSIS:Parameters returns empty parameters list."""
        result = parse_params(empty_params_open_close)
        assert result["parameters"] == []

    def test_empty_result_is_not_error(self, empty_params_self_closing):
        """Empty parameters should return success dict, not raise error."""
        result = parse_params(empty_params_self_closing)
        assert "error" not in result
        assert "parameters" in result


class TestParseParamsSingleParameter:
    """Tests for single parameter extraction (Requirement 5.1)."""

    def test_returns_one_parameter(self, single_param_file):
        """Single parameter file returns list with one entry."""
        result = parse_params(single_param_file)
        assert len(result["parameters"]) == 1

    def test_name_extracted(self, single_param_file):
        """Parameter name is extracted from SSIS:Name attribute."""
        result = parse_params(single_param_file)
        param = result["parameters"][0]
        assert param["name"] == "ServerName"

    def test_data_type_extracted(self, single_param_file):
        """Data type is extracted from DataType property."""
        result = parse_params(single_param_file)
        param = result["parameters"][0]
        assert param["data_type"] == "18"

    def test_default_value_extracted(self, single_param_file):
        """Default value is extracted from Value property."""
        result = parse_params(single_param_file)
        param = result["parameters"][0]
        assert param["default_value"] == "localhost"

    def test_sensitive_flag_extracted(self, single_param_file):
        """Sensitive flag extracted as boolean (False for '0')."""
        result = parse_params(single_param_file)
        param = result["parameters"][0]
        assert param["sensitive"] is False

    def test_required_flag_extracted(self, single_param_file):
        """Required flag extracted as boolean (True for '1')."""
        result = parse_params(single_param_file)
        param = result["parameters"][0]
        assert param["required"] is True


class TestParseParamsMultipleParameters:
    """Tests for multiple parameter extraction."""

    def test_all_parameters_extracted(self, multi_param_file):
        """All parameters in the file are extracted."""
        result = parse_params(multi_param_file)
        assert len(result["parameters"]) == 3

    def test_parameter_names_correct(self, multi_param_file):
        """All parameter names match expected values."""
        result = parse_params(multi_param_file)
        names = [p["name"] for p in result["parameters"]]
        assert names == ["ServerName", "DbPassword", "BatchSize"]

    def test_sensitive_parameter_flagged(self, multi_param_file):
        """Sensitive parameter has sensitive=True."""
        result = parse_params(multi_param_file)
        db_password = result["parameters"][1]
        assert db_password["name"] == "DbPassword"
        assert db_password["sensitive"] is True

    def test_non_sensitive_parameters_flagged_false(self, multi_param_file):
        """Non-sensitive parameters have sensitive=False."""
        result = parse_params(multi_param_file)
        assert result["parameters"][0]["sensitive"] is False
        assert result["parameters"][2]["sensitive"] is False

    def test_optional_parameter_not_required(self, multi_param_file):
        """BatchSize has required=False."""
        result = parse_params(multi_param_file)
        batch_size = result["parameters"][2]
        assert batch_size["required"] is False

    def test_integer_data_type(self, multi_param_file):
        """BatchSize has numeric data type '3' (i4)."""
        result = parse_params(multi_param_file)
        batch_size = result["parameters"][2]
        assert batch_size["data_type"] == "3"

    def test_empty_default_value(self, multi_param_file):
        """Sensitive parameter with empty value has empty string default_value."""
        result = parse_params(multi_param_file)
        db_password = result["parameters"][1]
        assert db_password["default_value"] == ""


class TestParseParamsRealFiles:
    """Tests against local example Project.params files, if present."""

    def test_real_sample_alpha_params(self):
        """Parse real SampleAlpha Project.params (empty)."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "examples",
            "SampleAlpha",
            "SampleAlpha",
            "Project.params",
        )
        if not os.path.isfile(path):
            pytest.skip("Example file not available")

        result = parse_params(path)
        assert result["parameters"] == []

    def test_real_sample_gamma_params(self):
        """Parse real SampleGamma Project.params (empty)."""
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "examples",
            "SampleGamma",
            "SampleGamma",
            "SampleGamma",
            "Project.params",
        )
        if not os.path.isfile(path):
            pytest.skip("Example file not available")

        result = parse_params(path)
        assert result["parameters"] == []
