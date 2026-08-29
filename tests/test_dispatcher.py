"""Unit tests for the file dispatcher module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from pydtsx_parser.dispatcher import (
    _build_cross_references,
    _extract_object_name,
    detect_file_type,
    dispatch,
    scan_directory,
)


class TestDetectFileType:
    """Tests for detect_file_type()."""

    def test_dtsx_extension(self):
        assert detect_file_type("Package.dtsx") == "dtsx_package"

    def test_dtproj_extension(self):
        assert detect_file_type("Project.dtproj") == "dtproj_project"

    def test_conmgr_extension(self):
        assert detect_file_type("DB.conmgr") == "conmgr_connection"

    def test_params_extension(self):
        assert detect_file_type("Project.params") == "params_parameters"

    def test_case_insensitive(self):
        assert detect_file_type("Package.DTSX") == "dtsx_package"
        assert detect_file_type("Project.DTPROJ") == "dtproj_project"
        assert detect_file_type("DB.CONMGR") == "conmgr_connection"
        assert detect_file_type("Project.PARAMS") == "params_parameters"

    def test_unsupported_extension_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported file extension"):
            detect_file_type("readme.txt")

    def test_no_extension_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported file extension"):
            detect_file_type("somefile")

    def test_full_path_with_supported_extension(self):
        assert detect_file_type("/path/to/dir/Package.dtsx") == "dtsx_package"


class TestScanDirectory:
    """Tests for scan_directory()."""

    def test_finds_supported_files(self, tmp_path):
        # Create various files
        (tmp_path / "pkg.dtsx").write_text("<xml/>")
        (tmp_path / "proj.dtproj").write_text("<xml/>")
        (tmp_path / "conn.conmgr").write_text("<xml/>")
        (tmp_path / "Project.params").write_text("<xml/>")
        (tmp_path / "readme.txt").write_text("ignore me")

        result = scan_directory(str(tmp_path))

        assert len(result) == 4
        names = [Path(f).name for f in result]
        assert "pkg.dtsx" in names
        assert "proj.dtproj" in names
        assert "conn.conmgr" in names
        assert "Project.params" in names
        assert "readme.txt" not in names

    def test_recursive_scan(self, tmp_path):
        # Create nested directories
        sub_dir = tmp_path / "subdir" / "nested"
        sub_dir.mkdir(parents=True)
        (tmp_path / "root.dtsx").write_text("<xml/>")
        (sub_dir / "nested.dtsx").write_text("<xml/>")

        result = scan_directory(str(tmp_path))

        assert len(result) == 2
        names = [Path(f).name for f in result]
        assert "root.dtsx" in names
        assert "nested.dtsx" in names

    def test_empty_directory(self, tmp_path):
        result = scan_directory(str(tmp_path))
        assert result == []

    def test_no_supported_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("nothing")
        (tmp_path / "data.csv").write_text("a,b,c")

        result = scan_directory(str(tmp_path))
        assert result == []

    def test_results_are_sorted(self, tmp_path):
        (tmp_path / "z_last.dtsx").write_text("<xml/>")
        (tmp_path / "a_first.dtsx").write_text("<xml/>")
        (tmp_path / "m_middle.dtsx").write_text("<xml/>")

        result = scan_directory(str(tmp_path))

        names = [Path(f).name for f in result]
        assert names == sorted(names)


class TestDispatch:
    """Tests for dispatch()."""

    def test_empty_path_raises_error(self):
        with pytest.raises(Exception):
            dispatch("")

    def test_none_path_raises_error(self):
        with pytest.raises(Exception):
            dispatch(None)

    def test_nonexistent_path_raises_error(self):
        with pytest.raises(Exception):
            dispatch("/nonexistent/path/to/file.dtsx")

    def test_single_dtsx_file(self, tmp_path):
        """Dispatch a minimal valid .dtsx file produces an envelope."""
        dtsx_content = (
            '<?xml version="1.0"?>\n'
            '<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
            'DTS:refId="Package" DTS:CreationName="Microsoft.Package" '
            'DTS:ObjectName="TestPackage" DTS:DTSID="{TEST-GUID}">'
            "</DTS:Executable>"
        )
        dtsx_file = tmp_path / "test.dtsx"
        dtsx_file.write_text(dtsx_content, encoding="utf-8")

        result = dispatch(str(dtsx_file))

        assert result["format_version"] == "1.0.0"
        assert result["file_type"] == "dtsx_package"
        assert "content" in result
        assert "source_file_metadata" in result
        assert "redaction_summary" in result

    def test_single_params_file(self, tmp_path):
        """Dispatch a minimal valid .params file."""
        params_content = (
            '<?xml version="1.0"?>\n'
            '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">'
            "</SSIS:Parameters>"
        )
        params_file = tmp_path / "Project.params"
        params_file.write_text(params_content, encoding="utf-8")

        result = dispatch(str(params_file))

        assert result["format_version"] == "1.0.0"
        assert result["file_type"] == "params_parameters"
        assert "content" in result

    def test_directory_dispatch(self, tmp_path):
        """Dispatch on a directory produces project-level output."""
        # Create a minimal dtsx file
        dtsx_content = (
            '<?xml version="1.0"?>\n'
            '<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
            'DTS:refId="Package" DTS:CreationName="Microsoft.Package" '
            'DTS:ObjectName="TestPackage" DTS:DTSID="{TEST-GUID}">'
            "</DTS:Executable>"
        )
        (tmp_path / "test.dtsx").write_text(dtsx_content, encoding="utf-8")

        # Create a minimal params file
        params_content = (
            '<?xml version="1.0"?>\n'
            '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">'
            "</SSIS:Parameters>"
        )
        (tmp_path / "Project.params").write_text(params_content, encoding="utf-8")

        result = dispatch(str(tmp_path))

        assert result["file_type"] == "project_directory"
        assert result["summary"]["total_files"] == 2
        assert result["summary"]["packages"] == 1
        assert result["summary"]["parameters"] == 1
        assert len(result["packages"]) == 1
        assert len(result["parameters"]) == 1

    def test_empty_directory_returns_empty_structure(self, tmp_path):
        """Empty directory returns empty project structure, not an error."""
        result = dispatch(str(tmp_path))

        assert result["file_type"] == "project_directory"
        assert result["summary"]["total_files"] == 0
        assert result["packages"] == []
        assert result["connection_managers"] == []
        assert result["parameters"] == []
        assert result["projects"] == []
        assert result["errors"] == []

    def test_unsupported_file_raises_value_error(self, tmp_path):
        """Dispatching an unsupported file directly raises ValueError."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("hello")

        with pytest.raises(ValueError, match="Unsupported file extension"):
            dispatch(str(txt_file))

    def test_directory_with_malformed_xml(self, tmp_path):
        """Directory with malformed XML file collects error."""
        (tmp_path / "bad.dtsx").write_text("not xml at all!!", encoding="utf-8")

        result = dispatch(str(tmp_path))

        assert result["file_type"] == "project_directory"
        assert result["summary"]["errors"] == 1
        assert len(result["errors"]) == 1
        assert result["errors"][0]["file_type"] == "dtsx_package"

    def test_directory_cross_references(self, tmp_path):
        """Directory dispatch builds cross-references by ObjectName."""
        # Package with a connection manager named "DB"
        dtsx_content = (
            '<?xml version="1.0"?>\n'
            '<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
            'DTS:refId="Package" DTS:CreationName="Microsoft.Package" '
            'DTS:ObjectName="TestPackage" DTS:DTSID="{TEST-GUID}">'
            "<DTS:ConnectionManagers>"
            '<DTS:ConnectionManager DTS:refId="Package.ConnectionManagers[DB]" '
            'DTS:CreationName="OLEDB" DTS:DTSID="{CONN-GUID}" '
            'DTS:ObjectName="DB">'
            "<DTS:ObjectData><DTS:ConnectionManager "
            'DTS:ConnectionString="Data Source=server;"/>'
            "</DTS:ObjectData>"
            "</DTS:ConnectionManager>"
            "</DTS:ConnectionManagers>"
            "</DTS:Executable>"
        )
        (tmp_path / "Package.dtsx").write_text(dtsx_content, encoding="utf-8")

        # Standalone connection manager named "DB"
        conmgr_content = (
            '<?xml version="1.0"?>\n'
            '<DTS:ConnectionManager xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
            'DTS:refId="Package.ConnectionManagers[DB]" '
            'DTS:CreationName="OLEDB" DTS:DTSID="{CONN-GUID}" '
            'DTS:ObjectName="DB">'
            "<DTS:ObjectData><DTS:ConnectionManager "
            'DTS:ConnectionString="Data Source=server;"/>'
            "</DTS:ObjectData>"
            "</DTS:ConnectionManager>"
        )
        (tmp_path / "DB.conmgr").write_text(conmgr_content, encoding="utf-8")

        result = dispatch(str(tmp_path))

        assert "cross_references" in result
        cross_refs = result["cross_references"]
        assert "connection_manager_index" in cross_refs
        assert "DB" in cross_refs["connection_manager_index"]

    def test_directory_dtproj_counted_as_project(self, tmp_path):
        """A valid .dtproj in a directory scan is grouped under 'projects'.

        A second file that sorts after it keeps the dispatch loop going
        past the .dtproj entry, rather than it happening to be the last
        file processed.
        """
        dtproj_content = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<Project>"
            "<DeploymentModel>Package</DeploymentModel>"
            "<ProductVersion>14.0.1000.100</ProductVersion>"
            "<SchemaVersion>8.0.0.0</SchemaVersion>"
            "</Project>"
        )
        (tmp_path / "AProject.dtproj").write_text(dtproj_content, encoding="utf-8")
        params_content = (
            '<?xml version="1.0"?>\n'
            '<SSIS:Parameters xmlns:SSIS="www.microsoft.com/SqlServer/SSIS">'
            "</SSIS:Parameters>"
        )
        (tmp_path / "ZProject.params").write_text(params_content, encoding="utf-8")

        result = dispatch(str(tmp_path))

        assert result["summary"]["projects"] == 1
        assert len(result["projects"]) == 1
        assert result["projects"][0]["file_type"] == "dtproj_project"

    def test_directory_parser_error_dict_collected(self, tmp_path):
        """A .dtproj missing required elements returns an error dict rather
        than raising — dispatch must collect that the same way it collects
        a raised SSISParseError, not append it as a successful project."""
        incomplete_dtproj = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<Project><ProductVersion>15.0.0.0</ProductVersion></Project>"
        )
        (tmp_path / "Incomplete.dtproj").write_text(incomplete_dtproj, encoding="utf-8")

        result = dispatch(str(tmp_path))

        assert result["summary"]["errors"] == 1
        assert result["summary"]["projects"] == 0
        assert result["errors"][0]["file_type"] == "dtproj_project"
        assert result["errors"][0]["error"]["error"] is True

    def test_directory_unexpected_exception_collected(self, tmp_path):
        """A non-SSISParseError raised mid-parse is still collected as an
        error entry instead of aborting the whole directory dispatch."""
        dtsx_content = (
            '<?xml version="1.0"?>\n'
            '<DTS:Executable xmlns:DTS="www.microsoft.com/SqlServer/Dts" '
            'DTS:refId="Package" DTS:CreationName="Microsoft.Package" '
            'DTS:ObjectName="TestPackage" DTS:DTSID="{TEST-GUID}">'
            "</DTS:Executable>"
        )
        (tmp_path / "test.dtsx").write_text(dtsx_content, encoding="utf-8")

        def _raise_unexpected(path: str) -> dict:
            raise RuntimeError("boom")

        with patch(
            "pydtsx_parser.dispatcher._EXTENSION_TO_PARSER",
            {".dtsx": _raise_unexpected},
        ):
            result = dispatch(str(tmp_path))

        assert result["summary"]["errors"] == 1
        assert result["errors"][0]["error"]["error_type"] == "unexpected_error"
        assert "boom" in result["errors"][0]["error"]["message"]


class TestExtractObjectName:
    """Tests for _extract_object_name helper."""

    def test_dtsx_object_name(self):
        content = {"package_attributes": {"object_name": "MyPackage"}}
        assert _extract_object_name(content, ".dtsx") == "MyPackage"

    def test_conmgr_object_name(self):
        content = {"connection_manager": {"object_name": "DB"}}
        assert _extract_object_name(content, ".conmgr") == "DB"

    def test_dtproj_object_name(self):
        content = {"manifest": {"project_properties": {"name": "MyProject"}}}
        assert _extract_object_name(content, ".dtproj") == "MyProject"

    def test_params_returns_none(self):
        content = {"parameters": []}
        assert _extract_object_name(content, ".params") is None

    def test_missing_attributes_returns_none(self):
        content = {}
        assert _extract_object_name(content, ".dtsx") is None

    def test_unrecognized_extension_returns_none(self):
        assert _extract_object_name({"anything": "here"}, ".unknown") is None

    def test_dtproj_manifest_explicitly_none_returns_none(self):
        """Regression test: parse_dtproj sets "manifest": None (not a
        missing key) for a .dtproj with no manifest section. content.get(
        "manifest", {}) does NOT fall back to {} in that case -- .get's
        default only applies to an absent key -- so this used to raise
        AttributeError: 'NoneType' object has no attribute 'get'."""
        content = {"manifest": None}
        assert _extract_object_name(content, ".dtproj") is None


class TestBuildCrossReferences:
    """Tests for _build_cross_references helper."""

    def test_empty_inputs(self):
        result = _build_cross_references([], [], [])
        assert result == {
            "connection_manager_index": {},
            "package_connection_references": {},
        }

    def test_connection_manager_index(self):
        conn_managers = [
            {
                "object_name": "DB",
                "file_path": "/path/to/DB.conmgr",
                "file_name": "DB.conmgr",
            }
        ]
        result = _build_cross_references([], conn_managers, [])
        assert "DB" in result["connection_manager_index"]
        assert result["connection_manager_index"]["DB"]["file_name"] == "DB.conmgr"

    def test_package_connection_references(self):
        packages = [
            {
                "object_name": "MyPackage",
                "file_name": "Package.dtsx",
                "content": {
                    "connection_managers": [
                        {"object_name": "DB"},
                        {"object_name": "DW"},
                    ]
                },
            }
        ]
        result = _build_cross_references(packages, [], [])
        assert "MyPackage" in result["package_connection_references"]
        assert result["package_connection_references"]["MyPackage"] == ["DB", "DW"]

    def test_connection_manager_without_object_name_skipped(self):
        """A conmgr entry with no ObjectName can't be indexed by name."""
        conn_managers = [{"file_path": "/x/DB.conmgr", "file_name": "DB.conmgr"}]
        result = _build_cross_references([], conn_managers, [])
        assert result["connection_manager_index"] == {}

    def test_package_connection_without_object_name_skipped(self):
        """A referenced connection manager with no ObjectName can't be
        listed, but a sibling one with a name still is."""
        packages = [
            {
                "object_name": "MyPackage",
                "content": {
                    "connection_managers": [
                        {"file_name": "anonymous.conmgr"},
                        {"object_name": "DB"},
                    ]
                },
            }
        ]
        result = _build_cross_references(packages, [], [])
        assert result["package_connection_references"]["MyPackage"] == ["DB"]
