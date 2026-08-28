"""Tests for pydtsx_parser.extractors.executables module."""

import xml.etree.ElementTree as ET

import pytest

from pydtsx_parser.extractors.executables import extract_executables

DTS_NS = "www.microsoft.com/SqlServer/Dts"


def _make_xml(xml_str: str) -> ET.Element:
    """Parse an XML string into an Element, with DTS namespace declared."""
    return ET.fromstring(xml_str)


# --- Fixtures ---


@pytest.fixture
def simple_executable_xml():
    """A parent element with a single executable."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables>
            <DTS:Executable
              DTS:refId="Package\\MyTask"
              DTS:CreationName="Microsoft.Pipeline"
              DTS:DTSID="{{ABCD-1234}}"
              DTS:ObjectName="MyTask"
              DTS:Disabled="False"
              DTS:Description="Data Flow Task">
              <DTS:Property DTS:Name="ForceExecValue">0</DTS:Property>
              <DTS:Variables />
            </DTS:Executable>
          </DTS:Executables>
        </DTS:Executable>
    ''')


@pytest.fixture
def nested_executables_xml():
    """A parent element with nested child executables (recursion)."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables>
            <DTS:Executable
              DTS:refId="Package\\Container"
              DTS:CreationName="STOCK:SEQUENCE"
              DTS:DTSID="{{CONT-1234}}"
              DTS:ObjectName="Container"
              DTS:Description="Sequence Container">
              <DTS:Variables />
              <DTS:Executables>
                <DTS:Executable
                  DTS:refId="Package\\Container\\ChildTask"
                  DTS:CreationName="Microsoft.Pipeline"
                  DTS:DTSID="{{CHILD-5678}}"
                  DTS:ObjectName="ChildTask"
                  DTS:Description="Child Data Flow">
                  <DTS:Variables />
                </DTS:Executable>
              </DTS:Executables>
            </DTS:Executable>
          </DTS:Executables>
        </DTS:Executable>
    ''')


@pytest.fixture
def executable_with_variables_xml():
    """An executable with task-level variables."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables>
            <DTS:Executable
              DTS:refId="Package\\MyTask"
              DTS:CreationName="Microsoft.Pipeline"
              DTS:DTSID="{{TASK-1234}}"
              DTS:ObjectName="MyTask">
              <DTS:Variables>
                <DTS:Variable DTS:ObjectName="Var1" DTS:Namespace="User">
                  <DTS:VariableValue DTS:DataType="8">Hello</DTS:VariableValue>
                </DTS:Variable>
              </DTS:Variables>
            </DTS:Executable>
          </DTS:Executables>
        </DTS:Executable>
    ''')


@pytest.fixture
def multiple_executables_xml():
    """A parent element with multiple sibling executables."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables>
            <DTS:Executable
              DTS:refId="Package\\Task1"
              DTS:CreationName="Microsoft.Pipeline"
              DTS:DTSID="{{T1-1234}}"
              DTS:ObjectName="Task1">
              <DTS:Variables />
            </DTS:Executable>
            <DTS:Executable
              DTS:refId="Package\\Task2"
              DTS:CreationName="Microsoft.ExecuteSQLTask"
              DTS:DTSID="{{T2-5678}}"
              DTS:ObjectName="Task2"
              DTS:Description="Run SQL">
              <DTS:Variables />
            </DTS:Executable>
            <DTS:Executable
              DTS:refId="Package\\Task3"
              DTS:CreationName="Microsoft.Pipeline"
              DTS:DTSID="{{T3-9012}}"
              DTS:ObjectName="Task3">
              <DTS:Variables />
            </DTS:Executable>
          </DTS:Executables>
        </DTS:Executable>
    ''')


@pytest.fixture
def disabled_executable_xml():
    """An executable with Disabled=True."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables>
            <DTS:Executable
              DTS:refId="Package\\DisabledTask"
              DTS:CreationName="Microsoft.Pipeline"
              DTS:DTSID="{{DIS-1234}}"
              DTS:ObjectName="DisabledTask"
              DTS:Disabled="True">
              <DTS:Variables />
            </DTS:Executable>
          </DTS:Executables>
        </DTS:Executable>
    ''')


@pytest.fixture
def no_executables_xml():
    """A parent element with no DTS:Executables child."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Variables />
        </DTS:Executable>
    ''')


@pytest.fixture
def empty_executables_xml():
    """A parent element with an empty DTS:Executables child."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables />
        </DTS:Executable>
    ''')


@pytest.fixture
def deeply_nested_xml():
    """Three levels of nested executables."""
    return _make_xml(f'''
        <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
          <DTS:Executables>
            <DTS:Executable
              DTS:refId="Package\\Level1"
              DTS:CreationName="STOCK:SEQUENCE"
              DTS:DTSID="{{L1}}"
              DTS:ObjectName="Level1">
              <DTS:Variables />
              <DTS:Executables>
                <DTS:Executable
                  DTS:refId="Package\\Level1\\Level2"
                  DTS:CreationName="STOCK:FORLOOP"
                  DTS:DTSID="{{L2}}"
                  DTS:ObjectName="Level2">
                  <DTS:Variables />
                  <DTS:Executables>
                    <DTS:Executable
                      DTS:refId="Package\\Level1\\Level2\\Level3"
                      DTS:CreationName="Microsoft.Pipeline"
                      DTS:DTSID="{{L3}}"
                      DTS:ObjectName="Level3">
                      <DTS:Variables />
                    </DTS:Executable>
                  </DTS:Executables>
                </DTS:Executable>
              </DTS:Executables>
            </DTS:Executable>
          </DTS:Executables>
        </DTS:Executable>
    ''')


# --- Tests ---


class TestExtractExecutables:
    """Tests for the extract_executables function."""

    def test_single_executable_basic_attributes(self, simple_executable_xml):
        """Extracts ref_id, creation_name, object_name, dts_id, executable_type."""
        result = extract_executables(simple_executable_xml)

        assert len(result) == 1
        exec_dict = result[0]
        assert exec_dict["ref_id"] == "Package\\MyTask"
        assert exec_dict["creation_name"] == "Microsoft.Pipeline"
        assert exec_dict["executable_type"] == "Microsoft.Pipeline"
        assert exec_dict["object_name"] == "MyTask"
        assert exec_dict["dts_id"] == "{ABCD-1234}"

    def test_disabled_flag_false(self, simple_executable_xml):
        """Disabled='False' converts to Python False."""
        result = extract_executables(simple_executable_xml)
        assert result[0]["disabled"] is False

    def test_disabled_flag_true(self, disabled_executable_xml):
        """Disabled='True' converts to Python True."""
        result = extract_executables(disabled_executable_xml)
        assert result[0]["disabled"] is True

    def test_disabled_default_when_absent(self, no_executables_xml):
        """When Disabled attribute is absent, defaults to False."""
        # Use an executable without the Disabled attribute
        xml = _make_xml(f'''
            <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
              <DTS:Executables>
                <DTS:Executable
                  DTS:refId="Package\\Task"
                  DTS:CreationName="Microsoft.Pipeline"
                  DTS:DTSID="{{ID}}"
                  DTS:ObjectName="Task">
                  <DTS:Variables />
                </DTS:Executable>
              </DTS:Executables>
            </DTS:Executable>
        ''')
        result = extract_executables(xml)
        assert result[0]["disabled"] is False

    def test_description_extracted(self, simple_executable_xml):
        """Description attribute is extracted when present."""
        result = extract_executables(simple_executable_xml)
        assert result[0]["description"] == "Data Flow Task"

    def test_description_omitted_when_absent(self, disabled_executable_xml):
        """Description is omitted (not null) when not present per Req 1.8."""
        result = extract_executables(disabled_executable_xml)
        assert "description" not in result[0]

    def test_properties_extracted(self, simple_executable_xml):
        """DTS:Property child elements are extracted with name and value."""
        result = extract_executables(simple_executable_xml)
        props = result[0]["properties"]
        assert len(props) == 1
        assert props[0]["name"] == "ForceExecValue"
        assert props[0]["value"] == "0"

    def test_properties_empty_when_none(self, disabled_executable_xml):
        """Properties list is empty when no DTS:Property children exist."""
        result = extract_executables(disabled_executable_xml)
        assert result[0]["properties"] == []

    def test_variables_extracted(self, executable_with_variables_xml):
        """Task-level variables are extracted via extract_variables."""
        result = extract_executables(executable_with_variables_xml)
        variables = result[0]["variables"]
        assert len(variables) == 1
        assert variables[0]["name"] == "Var1"
        assert variables[0]["namespace"] == "User"

    def test_variables_empty_when_no_content(self, simple_executable_xml):
        """Empty DTS:Variables returns empty list."""
        result = extract_executables(simple_executable_xml)
        assert result[0]["variables"] == []

    def test_multiple_executables(self, multiple_executables_xml):
        """Multiple sibling executables are all extracted."""
        result = extract_executables(multiple_executables_xml)
        assert len(result) == 3
        assert result[0]["object_name"] == "Task1"
        assert result[1]["object_name"] == "Task2"
        assert result[2]["object_name"] == "Task3"

    def test_nested_child_executables(self, nested_executables_xml):
        """Child executables are recursively extracted."""
        result = extract_executables(nested_executables_xml)

        assert len(result) == 1
        container = result[0]
        assert container["object_name"] == "Container"
        assert container["creation_name"] == "STOCK:SEQUENCE"

        children = container["child_executables"]
        assert len(children) == 1
        assert children[0]["object_name"] == "ChildTask"
        assert children[0]["creation_name"] == "Microsoft.Pipeline"
        assert children[0]["dts_id"] == "{CHILD-5678}"

    def test_deeply_nested_recursion(self, deeply_nested_xml):
        """Three levels of nested executables are properly extracted."""
        result = extract_executables(deeply_nested_xml)

        level1 = result[0]
        assert level1["object_name"] == "Level1"

        level2 = level1["child_executables"][0]
        assert level2["object_name"] == "Level2"
        assert level2["creation_name"] == "STOCK:FORLOOP"

        level3 = level2["child_executables"][0]
        assert level3["object_name"] == "Level3"
        assert level3["creation_name"] == "Microsoft.Pipeline"
        assert level3["child_executables"] == []

    def test_no_executables_element(self, no_executables_xml):
        """Returns empty list when no DTS:Executables element exists."""
        result = extract_executables(no_executables_xml)
        assert result == []

    def test_empty_executables_element(self, empty_executables_xml):
        """Returns empty list when DTS:Executables is empty."""
        result = extract_executables(empty_executables_xml)
        assert result == []

    def test_executable_type_matches_creation_name(self, simple_executable_xml):
        """executable_type field is the same as creation_name."""
        result = extract_executables(simple_executable_xml)
        exec_dict = result[0]
        assert exec_dict["executable_type"] == exec_dict["creation_name"]

    def test_multiple_properties(self):
        """Multiple DTS:Property children are all extracted."""
        xml = _make_xml(f'''
            <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
              <DTS:Executables>
                <DTS:Executable
                  DTS:refId="Package\\Task"
                  DTS:CreationName="Microsoft.Pipeline"
                  DTS:DTSID="{{ID}}"
                  DTS:ObjectName="Task">
                  <DTS:Property DTS:Name="ForceExecValue">0</DTS:Property>
                  <DTS:Property DTS:Name="ExecValueVariable"></DTS:Property>
                  <DTS:Property DTS:Name="ForceExecutionResult">-1</DTS:Property>
                  <DTS:Variables />
                </DTS:Executable>
              </DTS:Executables>
            </DTS:Executable>
        ''')
        result = extract_executables(xml)
        props = result[0]["properties"]
        assert len(props) == 3
        assert props[0] == {"name": "ForceExecValue", "value": "0"}
        assert props[1] == {"name": "ExecValueVariable", "value": ""}
        assert props[2] == {"name": "ForceExecutionResult", "value": "-1"}

    def test_disabled_case_insensitive(self):
        """Disabled attribute comparison is case-insensitive."""
        xml = _make_xml(f'''
            <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
              <DTS:Executables>
                <DTS:Executable
                  DTS:refId="Package\\Task"
                  DTS:CreationName="Microsoft.Pipeline"
                  DTS:DTSID="{{ID}}"
                  DTS:ObjectName="Task"
                  DTS:Disabled="TRUE">
                  <DTS:Variables />
                </DTS:Executable>
              </DTS:Executables>
            </DTS:Executable>
        ''')
        result = extract_executables(xml)
        assert result[0]["disabled"] is True

    def test_child_executables_empty_when_no_nested(self, simple_executable_xml):
        """child_executables is empty list when no nested DTS:Executables."""
        result = extract_executables(simple_executable_xml)
        assert result[0]["child_executables"] == []

    def test_real_world_structure(self):
        """Test with a structure matching realistic SSIS files."""
        xml = _make_xml(f'''
            <DTS:Executable xmlns:DTS="{DTS_NS}" DTS:ObjectName="Package">
              <DTS:Executables>
                <DTS:Executable
                  DTS:refId="Package\\Load Mapping Files"
                  DTS:CreationName="Microsoft.Pipeline"
                  DTS:Description="Data Flow Task"
                  DTS:DTSID="{{BF1EF785-1D36-4BA8-97F7-FF3092E34068}}"
                  DTS:ExecutableType="Microsoft.Pipeline"
                  DTS:LocaleID="-1"
                  DTS:ObjectName="Load Mapping Files">
                  <DTS:Variables />
                </DTS:Executable>
                <DTS:Executable
                  DTS:refId="Package\\Truncate Tables"
                  DTS:CreationName="Microsoft.DbMaintenanceTSQLExecuteTask"
                  DTS:Description="Execute T-SQL Statement Task"
                  DTS:DTSID="{{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}}"
                  DTS:ObjectName="Truncate Tables"
                  DTS:TaskContact="Execute T-SQL Statement Task">
                  <DTS:Variables />
                </DTS:Executable>
              </DTS:Executables>
            </DTS:Executable>
        ''')
        result = extract_executables(xml)

        assert len(result) == 2
        assert result[0]["object_name"] == "Load Mapping Files"
        assert result[0]["creation_name"] == "Microsoft.Pipeline"
        assert result[0]["description"] == "Data Flow Task"
        assert result[1]["object_name"] == "Truncate Tables"
        assert result[1]["creation_name"] == "Microsoft.DbMaintenanceTSQLExecuteTask"
