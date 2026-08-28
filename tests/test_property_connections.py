"""Property-based tests for connection manager extraction.

Uses Hypothesis to verify correctness properties of the connection manager
parser and extractor:
- Property 5: Connection Manager Type-Specific Extraction
- Property 6: Standalone/Inline Connection Manager Equivalence

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
"""

import os
import tempfile
import xml.etree.ElementTree as ET

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydtsx_parser.extractors.connections import (
    extract_connection_managers,
    extract_single_connection_manager,
)
from pydtsx_parser.parsers.conmgr import parse_conmgr

# DTS namespace used in SSIS files
DTS_NS = "www.microsoft.com/SqlServer/Dts"

# Recognized connection manager types
RECOGNIZED_TYPES = ["FLATFILE", "OLEDB", "ADO.NET:SQL", "ORACLE"]


# --- Strategies ---

# Strategy for safe attribute/identifier values (no XML-breaking chars)
safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="_-. /:",
    ),
    min_size=1,
    max_size=40,
)

# Strategy for object names (valid identifiers)
object_name_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="_-",
    ),
    min_size=1,
    max_size=20,
)

# Strategy for DTSID-like strings (GUID format)
dts_id_st = st.builds(
    lambda a, b, c, d, e: f"{{{a}-{b}-{c}-{d}-{e}}}",
    st.from_regex(r"[A-F0-9]{8}", fullmatch=True),
    st.from_regex(r"[A-F0-9]{4}", fullmatch=True),
    st.from_regex(r"[A-F0-9]{4}", fullmatch=True),
    st.from_regex(r"[A-F0-9]{4}", fullmatch=True),
    st.from_regex(r"[A-F0-9]{12}", fullmatch=True),
)

# Strategy for connection strings (key=value pairs)
connection_string_st = st.builds(
    lambda ds, ic, prov: f"Data Source={ds};Initial Catalog={ic};Provider={prov};",
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="_-."
        ),
        min_size=1,
        max_size=20,
    ),
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="_-"
        ),
        min_size=1,
        max_size=20,
    ),
    st.sampled_from(["MSOLEDBSQL.1", "SQLNCLI11.1", "SQLOLEDB.1"]),
)

# Strategy for file paths
file_path_st = st.builds(
    lambda d, f: f"C:\\data\\{d}\\{f}.csv",
    st.text(
        alphabet=st.characters(whitelist_categories=("L",)),
        min_size=1,
        max_size=10,
    ),
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="_-"
        ),
        min_size=1,
        max_size=15,
    ),
)

# Strategy for flat file column definitions
flat_file_column_st = st.fixed_dictionaries(
    {
        "name": object_name_st,
        "column_type": st.sampled_from(["Delimited", "FixedWidth"]),
        "delimiter": st.sampled_from(
            ["_x002C_", "_x0009_", "_x007C_", "_x000D__x000A_"]
        ),
        "data_type": st.sampled_from(["129", "130", "131", "4", "20"]),
        "max_width": st.integers(min_value=1, max_value=4000).map(str),
        "text_qualified": st.booleans(),
        "dts_id": dts_id_st,
    }
)

# Strategy for boolean values as they appear in SSIS XML
ssis_bool_st = st.sampled_from(["True", "False"])

# Strategy for Oracle server names
oracle_server_st = st.builds(
    lambda host, port, sid: f"{host}:{port}/{sid}",
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="-."
        ),
        min_size=3,
        max_size=20,
    ),
    st.sampled_from(["1521", "1522", "1525"]),
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N"), whitelist_characters="_."
        ),
        min_size=2,
        max_size=15,
    ),
)

# Strategy for unknown connection manager types (not matching recognized ones)
unknown_type_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=3,
    max_size=15,
).filter(lambda x: x.upper() not in ("FLATFILE", "OLEDB", "ADO.NET:SQL", "ORACLE"))

# Strategy for unknown property names (must be valid XML element names - ASCII letters only)
unknown_prop_name_st = st.text(
    alphabet=st.characters(
        whitelist_categories=(),
        whitelist_characters="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    ),
    min_size=2,
    max_size=15,
)

# Strategy for unknown property values (must not break XML)
unknown_prop_value_st = st.text(
    alphabet=st.characters(
        whitelist_categories=(),
        whitelist_characters="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-. /:;=",
    ),
    min_size=0,
    max_size=40,
)


# --- Helpers ---


def _build_flatfile_cm_xml(
    object_name: str,
    dts_id: str,
    file_path: str,
    columns: list[dict],
    description: str = "",
) -> str:
    """Build FLATFILE connection manager XML fragment."""
    desc_attr = f' DTS:Description="{_xml_escape(description)}"' if description else ""
    ref_id = f"Package.ConnectionManagers[{object_name}]"

    columns_xml = ""
    if columns:
        col_parts = []
        for col in columns:
            tq = "True" if col["text_qualified"] else "False"
            col_parts.append(
                f"        <DTS:FlatFileColumn\n"
                f'          DTS:ObjectName="{_xml_escape(col["name"])}"\n'
                f'          DTS:ColumnType="{col["column_type"]}"\n'
                f'          DTS:ColumnDelimiter="{col["delimiter"]}"\n'
                f'          DTS:DataType="{col["data_type"]}"\n'
                f'          DTS:MaximumWidth="{col["max_width"]}"\n'
                f'          DTS:TextQualified="{tq}"\n'
                f'          DTS:DTSID="{col["dts_id"]}" />'
            )
        columns_xml = (
            "      <DTS:FlatFileColumns>\n"
            + "\n".join(col_parts)
            + "\n      </DTS:FlatFileColumns>\n"
        )

    return (
        f'<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"\n'
        f'  DTS:refId="{ref_id}"\n'
        f'  DTS:CreationName="FLATFILE"\n'
        f'  DTS:DTSID="{dts_id}"\n'
        f'  DTS:ObjectName="{_xml_escape(object_name)}"{desc_attr}>\n'
        f"  <DTS:ObjectData>\n"
        f"    <DTS:ConnectionManager\n"
        f'      DTS:Format="Delimited"\n'
        f'      DTS:LocaleID="1033"\n'
        f'      DTS:HeaderRowDelimiter="_x000D__x000A_"\n'
        f'      DTS:ColumnNamesInFirstDataRow="True"\n'
        f'      DTS:RowDelimiter=""\n'
        f'      DTS:CodePage="65001"\n'
        f'      DTS:ConnectionString="{_xml_escape(file_path)}">\n'
        f"{columns_xml}"
        f"    </DTS:ConnectionManager>\n"
        f"  </DTS:ObjectData>\n"
        f"</DTS:ConnectionManager>"
    )


def _build_oledb_cm_xml(
    object_name: str,
    dts_id: str,
    connection_string: str,
    description: str = "",
) -> str:
    """Build OLEDB connection manager XML fragment."""
    desc_attr = f' DTS:Description="{_xml_escape(description)}"' if description else ""
    ref_id = f"Package.ConnectionManagers[{object_name}]"

    return (
        f'<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"\n'
        f'  DTS:refId="{ref_id}"\n'
        f'  DTS:CreationName="OLEDB"\n'
        f'  DTS:DTSID="{dts_id}"\n'
        f'  DTS:ObjectName="{_xml_escape(object_name)}"{desc_attr}>\n'
        f"  <DTS:ObjectData>\n"
        f"    <DTS:ConnectionManager\n"
        f'      DTS:ConnectionString="{_xml_escape(connection_string)}" />\n'
        f"  </DTS:ObjectData>\n"
        f"</DTS:ConnectionManager>"
    )


def _build_adonet_cm_xml(
    object_name: str,
    dts_id: str,
    connection_string: str,
    description: str = "",
) -> str:
    """Build ADO.NET:SQL connection manager XML fragment."""
    desc_attr = f' DTS:Description="{_xml_escape(description)}"' if description else ""
    ref_id = f"Package.ConnectionManagers[{object_name}]"

    return (
        f'<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"\n'
        f'  DTS:refId="{ref_id}"\n'
        f'  DTS:CreationName="ADO.NET:SQL"\n'
        f'  DTS:DTSID="{dts_id}"\n'
        f'  DTS:ObjectName="{_xml_escape(object_name)}"{desc_attr}>\n'
        f"  <DTS:ObjectData>\n"
        f"    <DTS:ConnectionManager\n"
        f'      DTS:ConnectionString="{_xml_escape(connection_string)}" />\n'
        f"  </DTS:ObjectData>\n"
        f"</DTS:ConnectionManager>"
    )


def _build_oracle_cm_xml(
    object_name: str,
    dts_id: str,
    server_name: str,
    user_name: str,
    oracle_home: str,
    oracle_home_64: str,
    win_auth: str,
    retain: str,
    initial_catalog: str,
    enable_tracing: str,
    description: str = "",
) -> str:
    """Build ORACLE connection manager XML fragment."""
    desc_attr = f' DTS:Description="{_xml_escape(description)}"' if description else ""
    ref_id = f"Package.ConnectionManagers[{object_name}]"
    conn_str = f"SERVER={server_name};USERNAME={user_name};"

    return (
        f'<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"\n'
        f'  DTS:refId="{ref_id}"\n'
        f'  DTS:CreationName="ORACLE"\n'
        f'  DTS:DTSID="{dts_id}"\n'
        f'  DTS:ObjectName="{_xml_escape(object_name)}"{desc_attr}>\n'
        f"  <DTS:ObjectData>\n"
        f"    <DTS:ConnectionManager>\n"
        f"      <OraConnectionString>{_xml_escape(conn_str)}</OraConnectionString>\n"
        f'      <OraPassword Sensitive="1">encrypted_data</OraPassword>\n'
        f"      <OraRetain>{retain}</OraRetain>\n"
        f"      <OraInitialCatalog>{_xml_escape(initial_catalog)}</OraInitialCatalog>\n"
        f"      <OraServerName>{_xml_escape(server_name)}</OraServerName>\n"
        f"      <OraUserName>{_xml_escape(user_name)}</OraUserName>\n"
        f"      <OraOracleHome>{_xml_escape(oracle_home)}</OraOracleHome>\n"
        f"      <OraOracleHome64>{_xml_escape(oracle_home_64)}</OraOracleHome64>\n"
        f"      <OraWinAuthentication>{win_auth}</OraWinAuthentication>\n"
        f"      <OraEnableDetailedTracing>{enable_tracing}</OraEnableDetailedTracing>\n"
        f"    </DTS:ConnectionManager>\n"
        f"  </DTS:ObjectData>\n"
        f"</DTS:ConnectionManager>"
    )


def _build_unknown_cm_xml(
    object_name: str,
    dts_id: str,
    creation_name: str,
    child_properties: dict[str, str],
    description: str = "",
) -> str:
    """Build unknown-type connection manager XML fragment with child elements."""
    desc_attr = f' DTS:Description="{_xml_escape(description)}"' if description else ""
    ref_id = f"Package.ConnectionManagers[{object_name}]"

    children_xml = ""
    if child_properties:
        parts = []
        for name, value in child_properties.items():
            parts.append(f"      <{name}>{_xml_escape(value)}</{name}>")
        children_xml = "\n".join(parts) + "\n"

    return (
        f'<DTS:ConnectionManager xmlns:DTS="{DTS_NS}"\n'
        f'  DTS:refId="{ref_id}"\n'
        f'  DTS:CreationName="{_xml_escape(creation_name)}"\n'
        f'  DTS:DTSID="{dts_id}"\n'
        f'  DTS:ObjectName="{_xml_escape(object_name)}"{desc_attr}>\n'
        f"  <DTS:ObjectData>\n"
        f"    <DTS:ConnectionManager>\n"
        f"{children_xml}"
        f"    </DTS:ConnectionManager>\n"
        f"  </DTS:ObjectData>\n"
        f"</DTS:ConnectionManager>"
    )


def _wrap_inline(cm_xml: str) -> str:
    """Wrap a connection manager XML in a full .dtsx package structure."""
    return (
        f'<?xml version="1.0"?>\n'
        f'<DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">\n'
        f"  <DTS:ConnectionManagers>\n"
        f"    {cm_xml}\n"
        f"  </DTS:ConnectionManagers>\n"
        f"</DTS:Executable>"
    )


def _wrap_standalone(cm_xml: str) -> str:
    """Wrap a connection manager XML as a standalone .conmgr file."""
    return f'<?xml version="1.0"?>\n{cm_xml}'


def _write_temp_file(xml_content: str, suffix: str) -> str:
    """Write XML content to a temporary file and return the path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, xml_content.encode("utf-8"))
    finally:
        os.close(fd)
    return path


def _xml_escape(value: str) -> str:
    """Escape XML special characters in attribute values and text."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# --- Property 5: Connection Manager Type-Specific Extraction ---
# Feature: pydtsx-parser, Property 5: Connection Manager Type-Specific Extraction


class TestPropertyConnectionManagerTypeSpecificExtraction:
    """Property 5: Connection Manager Type-Specific Extraction.

    For any connection manager with a recognized CreationName (FLATFILE, OLEDB,
    ADO.NET:SQL, ORACLE) or an unrecognized CreationName, the parser SHALL extract
    the ObjectName, DTSID, and all nested ObjectData properties without loss,
    including type-specific fields.

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6**
    """

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        file_path=file_path_st,
        columns=st.lists(flat_file_column_st, min_size=0, max_size=5),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_flatfile_extracts_all_properties(
        self, object_name, dts_id, file_path, columns
    ):
        """FLATFILE connection managers extract ObjectName, DTSID, and all columns.

        **Validates: Requirements 3.1**
        """
        # Feature: pydtsx-parser, Property 5: Connection Manager Type-Specific Extraction
        xml = _build_flatfile_cm_xml(object_name, dts_id, file_path, columns)
        element = ET.fromstring(xml)

        result = extract_single_connection_manager(element, "test.dtsx")

        # Common fields extracted
        assert result["object_name"] == object_name
        assert result["dts_id"] == dts_id
        assert result["creation_name"] == "FLATFILE"

        # Properties extracted
        props = result["properties"]
        assert props["format"] == "Delimited"
        assert props["connection_string"] == file_path
        assert props["code_page"] == "65001"

        # Columns extracted without loss
        if columns:
            assert "flat_file_columns" in props
            assert len(props["flat_file_columns"]) == len(columns)
            for i, col in enumerate(columns):
                extracted_col = props["flat_file_columns"][i]
                assert extracted_col["object_name"] == col["name"]
                assert extracted_col["column_type"] == col["column_type"]
                assert extracted_col["data_type"] == col["data_type"]
                assert extracted_col["maximum_width"] == col["max_width"]
                assert extracted_col["dts_id"] == col["dts_id"]

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        connection_string=connection_string_st,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_oledb_extracts_full_connection_string(
        self, object_name, dts_id, connection_string
    ):
        """OLEDB connection managers extract full connection string without loss.

        **Validates: Requirements 3.2**
        """
        # Feature: pydtsx-parser, Property 5: Connection Manager Type-Specific Extraction
        xml = _build_oledb_cm_xml(object_name, dts_id, connection_string)
        element = ET.fromstring(xml)

        result = extract_single_connection_manager(element, "test.dtsx")

        assert result["object_name"] == object_name
        assert result["dts_id"] == dts_id
        assert result["creation_name"] == "OLEDB"
        assert result["properties"]["connection_string"] == connection_string

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        connection_string=connection_string_st,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_adonet_extracts_full_connection_string(
        self, object_name, dts_id, connection_string
    ):
        """ADO.NET:SQL connection managers extract full connection string without loss.

        **Validates: Requirements 3.2**
        """
        # Feature: pydtsx-parser, Property 5: Connection Manager Type-Specific Extraction
        xml = _build_adonet_cm_xml(object_name, dts_id, connection_string)
        element = ET.fromstring(xml)

        result = extract_single_connection_manager(element, "test.dtsx")

        assert result["object_name"] == object_name
        assert result["dts_id"] == dts_id
        assert result["creation_name"] == "ADO.NET:SQL"
        assert result["properties"]["connection_string"] == connection_string

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        server_name=oracle_server_st,
        user_name=object_name_st,
        oracle_home=safe_text,
        oracle_home_64=safe_text,
        win_auth=ssis_bool_st,
        retain=ssis_bool_st,
        initial_catalog=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=0,
            max_size=15,
        ),
        enable_tracing=ssis_bool_st,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_oracle_extracts_all_specific_properties(
        self,
        object_name,
        dts_id,
        server_name,
        user_name,
        oracle_home,
        oracle_home_64,
        win_auth,
        retain,
        initial_catalog,
        enable_tracing,
    ):
        """ORACLE connection managers extract server, user, home paths, and flags.

        **Validates: Requirements 3.3**
        """
        # Feature: pydtsx-parser, Property 5: Connection Manager Type-Specific Extraction
        xml = _build_oracle_cm_xml(
            object_name,
            dts_id,
            server_name,
            user_name,
            oracle_home,
            oracle_home_64,
            win_auth,
            retain,
            initial_catalog,
            enable_tracing,
        )
        element = ET.fromstring(xml)

        result = extract_single_connection_manager(element, "test.dtsx")

        assert result["object_name"] == object_name
        assert result["dts_id"] == dts_id
        assert result["creation_name"] == "ORACLE"

        props = result["properties"]
        assert props["server_name"] == server_name
        assert props["user_name"] == user_name
        assert props["oracle_home"] == oracle_home
        assert props["oracle_home_64"] == oracle_home_64
        assert props["win_authentication"] == (win_auth == "True")
        assert props["retain"] == (retain == "True")
        assert props["initial_catalog"] == initial_catalog
        assert props["enable_detailed_tracing"] == (enable_tracing == "True")
        # Password is always extracted with sensitive flag
        assert props["password"]["sensitive"] is True
        # Connection string is composed from server and user
        expected_conn_str = f"SERVER={server_name};USERNAME={user_name};"
        assert props["connection_string"] == expected_conn_str

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        creation_name=unknown_type_st,
        child_properties=st.dictionaries(
            unknown_prop_name_st,
            unknown_prop_value_st,
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unknown_type_extracts_all_objectdata_properties(
        self, object_name, dts_id, creation_name, child_properties
    ):
        """Unknown types extract ObjectName, DTSID, and all nested properties.

        **Validates: Requirements 3.6**
        """
        # Feature: pydtsx-parser, Property 5: Connection Manager Type-Specific Extraction
        xml = _build_unknown_cm_xml(
            object_name, dts_id, creation_name, child_properties
        )
        element = ET.fromstring(xml)

        result = extract_single_connection_manager(element, "test.dtsx")

        assert result["object_name"] == object_name
        assert result["dts_id"] == dts_id
        assert result["creation_name"] == creation_name

        # All child properties should be in the extracted properties
        props = result["properties"]
        for prop_name, prop_value in child_properties.items():
            assert prop_name in props, (
                f"Property '{prop_name}' not found in extracted properties: {props}"
            )
            assert props[prop_name] == prop_value, (
                f"Property '{prop_name}': expected '{prop_value}', got '{props[prop_name]}'"
            )


# --- Property 6: Standalone/Inline Connection Manager Equivalence ---
# Feature: pydtsx-parser, Property 6: Standalone/Inline Connection Manager Equivalence


class TestPropertyStandaloneInlineEquivalence:
    """Property 6: Standalone/Inline Connection Manager Equivalence.

    For any connection manager definition, parsing it as a standalone .conmgr
    file SHALL produce output containing the same attributes and nested properties
    as parsing an equivalent inline connection manager within a .dtsx package.

    **Validates: Requirements 3.5**
    """

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        connection_string=connection_string_st,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_oledb_standalone_equals_inline(
        self, object_name, dts_id, connection_string
    ):
        """OLEDB parsed as .conmgr produces same attributes as inline within .dtsx.

        **Validates: Requirements 3.5**
        """
        # Feature: pydtsx-parser, Property 6: Standalone/Inline Connection Manager Equivalence
        cm_xml = _build_oledb_cm_xml(object_name, dts_id, connection_string)

        # Parse as standalone .conmgr
        standalone_path = _write_temp_file(_wrap_standalone(cm_xml), ".conmgr")
        try:
            standalone_result = parse_conmgr(standalone_path)
            standalone_cm = standalone_result["connection_manager"]
        finally:
            os.unlink(standalone_path)

        # Parse as inline within a .dtsx package
        inline_xml = _wrap_inline(cm_xml)
        inline_root = ET.fromstring(inline_xml)
        inline_cms = extract_connection_managers(inline_root, "test.dtsx")
        assert len(inline_cms) == 1
        inline_cm = inline_cms[0]

        # Verify equivalence of attributes and properties
        assert standalone_cm["object_name"] == inline_cm["object_name"]
        assert standalone_cm["dts_id"] == inline_cm["dts_id"]
        assert standalone_cm["creation_name"] == inline_cm["creation_name"]
        assert standalone_cm["properties"] == inline_cm["properties"]

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        server_name=oracle_server_st,
        user_name=object_name_st,
        oracle_home=safe_text,
        oracle_home_64=safe_text,
        win_auth=ssis_bool_st,
        retain=ssis_bool_st,
        initial_catalog=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N")),
            min_size=0,
            max_size=15,
        ),
        enable_tracing=ssis_bool_st,
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_oracle_standalone_equals_inline(
        self,
        object_name,
        dts_id,
        server_name,
        user_name,
        oracle_home,
        oracle_home_64,
        win_auth,
        retain,
        initial_catalog,
        enable_tracing,
    ):
        """ORACLE parsed as .conmgr produces same attributes as inline within .dtsx.

        **Validates: Requirements 3.5**
        """
        # Feature: pydtsx-parser, Property 6: Standalone/Inline Connection Manager Equivalence
        cm_xml = _build_oracle_cm_xml(
            object_name,
            dts_id,
            server_name,
            user_name,
            oracle_home,
            oracle_home_64,
            win_auth,
            retain,
            initial_catalog,
            enable_tracing,
        )

        # Parse as standalone .conmgr
        standalone_path = _write_temp_file(_wrap_standalone(cm_xml), ".conmgr")
        try:
            standalone_result = parse_conmgr(standalone_path)
            standalone_cm = standalone_result["connection_manager"]
        finally:
            os.unlink(standalone_path)

        # Parse as inline within a .dtsx package
        inline_xml = _wrap_inline(cm_xml)
        inline_root = ET.fromstring(inline_xml)
        inline_cms = extract_connection_managers(inline_root, "test.dtsx")
        assert len(inline_cms) == 1
        inline_cm = inline_cms[0]

        # Verify equivalence of attributes and properties
        assert standalone_cm["object_name"] == inline_cm["object_name"]
        assert standalone_cm["dts_id"] == inline_cm["dts_id"]
        assert standalone_cm["creation_name"] == inline_cm["creation_name"]
        assert standalone_cm["properties"] == inline_cm["properties"]

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        file_path=file_path_st,
        columns=st.lists(flat_file_column_st, min_size=0, max_size=3),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_flatfile_standalone_equals_inline(
        self, object_name, dts_id, file_path, columns
    ):
        """FLATFILE parsed as .conmgr produces same attributes as inline within .dtsx.

        **Validates: Requirements 3.5**
        """
        # Feature: pydtsx-parser, Property 6: Standalone/Inline Connection Manager Equivalence
        cm_xml = _build_flatfile_cm_xml(object_name, dts_id, file_path, columns)

        # Parse as standalone .conmgr
        standalone_path = _write_temp_file(_wrap_standalone(cm_xml), ".conmgr")
        try:
            standalone_result = parse_conmgr(standalone_path)
            standalone_cm = standalone_result["connection_manager"]
        finally:
            os.unlink(standalone_path)

        # Parse as inline within a .dtsx package
        inline_xml = _wrap_inline(cm_xml)
        inline_root = ET.fromstring(inline_xml)
        inline_cms = extract_connection_managers(inline_root, "test.dtsx")
        assert len(inline_cms) == 1
        inline_cm = inline_cms[0]

        # Verify equivalence of attributes and properties
        assert standalone_cm["object_name"] == inline_cm["object_name"]
        assert standalone_cm["dts_id"] == inline_cm["dts_id"]
        assert standalone_cm["creation_name"] == inline_cm["creation_name"]
        assert standalone_cm["properties"] == inline_cm["properties"]

    @given(
        object_name=object_name_st,
        dts_id=dts_id_st,
        creation_name=unknown_type_st,
        child_properties=st.dictionaries(
            unknown_prop_name_st,
            unknown_prop_value_st,
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_unknown_type_standalone_equals_inline(
        self, object_name, dts_id, creation_name, child_properties
    ):
        """Unknown types parsed as .conmgr produce same output as inline within .dtsx.

        **Validates: Requirements 3.5**
        """
        # Feature: pydtsx-parser, Property 6: Standalone/Inline Connection Manager Equivalence
        cm_xml = _build_unknown_cm_xml(
            object_name, dts_id, creation_name, child_properties
        )

        # Parse as standalone .conmgr
        standalone_path = _write_temp_file(_wrap_standalone(cm_xml), ".conmgr")
        try:
            standalone_result = parse_conmgr(standalone_path)
            standalone_cm = standalone_result["connection_manager"]
        finally:
            os.unlink(standalone_path)

        # Parse as inline within a .dtsx package
        inline_xml = _wrap_inline(cm_xml)
        inline_root = ET.fromstring(inline_xml)
        inline_cms = extract_connection_managers(inline_root, "test.dtsx")
        assert len(inline_cms) == 1
        inline_cm = inline_cms[0]

        # Verify equivalence of attributes and properties
        assert standalone_cm["object_name"] == inline_cm["object_name"]
        assert standalone_cm["dts_id"] == inline_cm["dts_id"]
        assert standalone_cm["creation_name"] == inline_cm["creation_name"]
        assert standalone_cm["properties"] == inline_cm["properties"]
