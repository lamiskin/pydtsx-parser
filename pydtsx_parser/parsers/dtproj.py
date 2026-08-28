"""DTPROJ project file parser.

Parses .dtproj files to extract project-level metadata including deployment
model, product version, schema version, database reference, manifest section
(ProtectionLevel, project properties, packages, connection managers),
ProjectConnectionParameters, and PackageInfo.

Returns an error dict on malformed XML or missing required elements
(DeploymentModel, ProductVersion, SchemaVersion).
"""

import xml.etree.ElementTree as ET

from pydtsx_parser.constants import NAMESPACES
from pydtsx_parser.xml_utils import (
    count_elements_and_attributes,
    get_root,
    parse_xml,
)

# Namespace URI for SSIS elements/attributes
_SSIS_NS = NAMESPACES["SSIS"]


def parse_dtproj(file_path: str) -> dict:
    """Parse a .dtproj file and return structured project metadata.

    Orchestrates the full extraction pipeline:
    1. Parse XML (handles file not found / malformed XML errors)
    2. Extract required top-level elements (DeploymentModel, ProductVersion, SchemaVersion)
    3. Extract database reference
    4. Extract manifest section (ProtectionLevel, properties, packages, connection managers)
    5. Extract ProjectConnectionParameters
    6. Extract PackageInfo
    7. Compute completeness summary

    Args:
        file_path: Path to the .dtproj file to parse.

    Returns:
        Dict with keys: success, deployment_model, product_version,
        schema_version, database, manifest, project_connection_parameters,
        package_info, completeness_summary.

        On error, returns dict with: error=True, file_path, error_type, message, details.

    Raises:
        FileNotFoundError: If the file does not exist or path is null/empty.
        MalformedXMLError: If the file contains malformed XML.
    """
    # Step 1: Parse XML (raises FileNotFoundError or MalformedXMLError)
    tree = parse_xml(file_path)
    root = get_root(tree, file_path)

    # Step 2: Extract required top-level elements
    deployment_model = _get_required_element_text(root, "DeploymentModel")
    product_version = _get_required_element_text(root, "ProductVersion")
    schema_version = _get_required_element_text(root, "SchemaVersion")

    # Check for missing required elements
    missing = []
    if deployment_model is None:
        missing.append("DeploymentModel")
    if product_version is None:
        missing.append("ProductVersion")
    if schema_version is None:
        missing.append("SchemaVersion")

    if missing:
        return {
            "error": True,
            "file_path": file_path,
            "error_type": "extraction_error",
            "message": f"Missing required elements: {', '.join(missing)}",
            "details": f"The .dtproj file is missing required elements: {', '.join(missing)}",
        }

    # Step 3: Extract database reference
    database = _extract_database(root)

    # Step 4: Extract manifest section
    manifest = _extract_manifest(root)

    # Step 5: Extract ProjectConnectionParameters
    project_connection_parameters = _extract_project_connection_parameters(root)

    # Step 6: Extract PackageInfo
    package_info = _extract_package_info(root)

    # Step 7: Compute completeness summary
    total_elements, total_attributes, skipped_items = count_elements_and_attributes(
        tree
    )
    completeness_summary = {
        "total_elements": total_elements,
        "total_attributes": total_attributes,
        "skipped_items": skipped_items,
    }

    return {
        "success": True,
        "deployment_model": deployment_model,
        "product_version": product_version,
        "schema_version": schema_version,
        "database": database,
        "manifest": manifest,
        "project_connection_parameters": project_connection_parameters,
        "package_info": package_info,
        "completeness_summary": completeness_summary,
    }


def _get_required_element_text(root: ET.Element, tag_name: str) -> str | None:
    """Get text content of a direct child element by tag name.

    Searches for elements without namespace (dtproj root elements are
    not namespace-prefixed).

    Args:
        root: The root XML element.
        tag_name: The local tag name to find.

    Returns:
        The text content of the element, or None if not found.
    """
    elem = root.find(tag_name)
    if elem is None:
        return None
    return elem.text or ""


def _extract_database(root: ET.Element) -> dict | None:
    """Extract database reference from the Database element.

    Args:
        root: The root XML element.

    Returns:
        Dict with 'name' and 'full_path' keys, or None if no Database element.
    """
    db_elem = root.find("Database")
    if db_elem is None:
        return None

    name_elem = db_elem.find("Name")
    path_elem = db_elem.find("FullPath")

    return {
        "name": name_elem.text if name_elem is not None else "",
        "full_path": path_elem.text if path_elem is not None else "",
    }


def _extract_manifest(root: ET.Element) -> dict | None:
    """Extract the manifest section from DeploymentModelSpecificContent.

    The manifest contains:
    - ProtectionLevel attribute on the SSIS:Project element
    - Project properties (ID, Name, VersionMajor, etc.)
    - Package references with entry point flags
    - Connection manager references

    Args:
        root: The root XML element.

    Returns:
        Dict with manifest data, or None if no manifest found.
    """
    # Navigate: DeploymentModelSpecificContent > Manifest > SSIS:Project
    deploy_content = root.find("DeploymentModelSpecificContent")
    if deploy_content is None:
        return None

    manifest_elem = deploy_content.find("Manifest")
    if manifest_elem is None:
        return None

    # Find SSIS:Project element
    project_elem = manifest_elem.find(f"{{{_SSIS_NS}}}Project")
    if project_elem is None:
        return None

    # Extract ProtectionLevel
    protection_level = project_elem.get(f"{{{_SSIS_NS}}}ProtectionLevel", "")

    # Extract project properties
    project_properties = _extract_project_properties(project_elem)

    # Extract packages
    packages = _extract_packages(project_elem)

    # Extract connection managers
    connection_managers = _extract_connection_manager_refs(project_elem)

    return {
        "protection_level": protection_level,
        "project_properties": project_properties,
        "packages": packages,
        "connection_managers": connection_managers,
    }


def _extract_project_properties(project_elem: ET.Element) -> dict:
    """Extract project properties from SSIS:Properties section.

    Extracts known properties: ID, Name, VersionMajor, VersionMinor,
    VersionBuild, VersionComments, CreationDate, CreatorName,
    CreatorComputerName, Description, FormatVersion.

    Args:
        project_elem: The SSIS:Project element.

    Returns:
        Dict mapping property names (snake_case) to their values.
    """
    properties_elem = project_elem.find(f"{{{_SSIS_NS}}}Properties")
    if properties_elem is None:
        return {}

    # Map SSIS property names to output key names
    property_map = {
        "ID": "id",
        "Name": "name",
        "VersionMajor": "version_major",
        "VersionMinor": "version_minor",
        "VersionBuild": "version_build",
        "VersionComments": "version_comments",
        "CreationDate": "creation_date",
        "CreatorName": "creator_name",
        "CreatorComputerName": "creator_computer_name",
        "Description": "description",
        "FormatVersion": "format_version",
    }

    result = {}
    for prop_elem in properties_elem.findall(f"{{{_SSIS_NS}}}Property"):
        prop_name = prop_elem.get(f"{{{_SSIS_NS}}}Name", "")
        if prop_name in property_map:
            value = prop_elem.text or ""
            # Strip whitespace for cleaner output
            result[property_map[prop_name]] = value.strip()

    return result


def _extract_packages(project_elem: ET.Element) -> list[dict]:
    """Extract package references from SSIS:Packages section.

    Each package has a name and entry point flag.

    Args:
        project_elem: The SSIS:Project element.

    Returns:
        List of dicts with 'name' and 'entry_point' keys.
    """
    packages_elem = project_elem.find(f"{{{_SSIS_NS}}}Packages")
    if packages_elem is None:
        return []

    packages = []
    for pkg_elem in packages_elem.findall(f"{{{_SSIS_NS}}}Package"):
        name = pkg_elem.get(f"{{{_SSIS_NS}}}Name", "")
        entry_point_str = pkg_elem.get(f"{{{_SSIS_NS}}}EntryPoint", "0")
        entry_point = entry_point_str == "1"
        packages.append({"name": name, "entry_point": entry_point})

    return packages


def _extract_connection_manager_refs(project_elem: ET.Element) -> list[dict]:
    """Extract connection manager file references from SSIS:ConnectionManagers.

    Args:
        project_elem: The SSIS:Project element.

    Returns:
        List of dicts with 'name' key for each connection manager reference.
    """
    cm_elem = project_elem.find(f"{{{_SSIS_NS}}}ConnectionManagers")
    if cm_elem is None:
        return []

    managers = []
    for cm in cm_elem.findall(f"{{{_SSIS_NS}}}ConnectionManager"):
        name = cm.get(f"{{{_SSIS_NS}}}Name", "")
        managers.append({"name": name})

    return managers


def _extract_project_connection_parameters(root: ET.Element) -> list[dict]:
    """Extract ProjectConnectionParameters from the deployment info section.

    Navigation path:
    DeploymentModelSpecificContent > Manifest > SSIS:Project >
    SSIS:DeploymentInfo > SSIS:ProjectConnectionParameters > SSIS:Parameter

    Each parameter has: name, data_type, sensitivity, required,
    include_in_debug_dump, and value (if non-sensitive).

    Args:
        root: The root XML element.

    Returns:
        List of parameter dicts.
    """
    # Navigate to ProjectConnectionParameters
    deploy_content = root.find("DeploymentModelSpecificContent")
    if deploy_content is None:
        return []

    manifest_elem = deploy_content.find("Manifest")
    if manifest_elem is None:
        return []

    project_elem = manifest_elem.find(f"{{{_SSIS_NS}}}Project")
    if project_elem is None:
        return []

    deployment_info = project_elem.find(f"{{{_SSIS_NS}}}DeploymentInfo")
    if deployment_info is None:
        return []

    pcp_elem = deployment_info.find(f"{{{_SSIS_NS}}}ProjectConnectionParameters")
    if pcp_elem is None:
        return []

    return _extract_parameters(pcp_elem)


def _extract_parameters(container_elem: ET.Element) -> list[dict]:
    """Extract SSIS:Parameter elements from a container.

    Each parameter has SSIS:Properties containing:
    - DataType, Sensitive, Required, IncludeInDebugDump, Value

    Args:
        container_elem: Element containing SSIS:Parameter children.

    Returns:
        List of parameter dicts.
    """
    parameters: list[dict[str, object]] = []
    for param_elem in container_elem.findall(f"{{{_SSIS_NS}}}Parameter"):
        param_name = param_elem.get(f"{{{_SSIS_NS}}}Name", "")

        # Extract properties from SSIS:Properties
        props_elem = param_elem.find(f"{{{_SSIS_NS}}}Properties")
        if props_elem is None:
            parameters.append({"name": param_name})
            continue

        # Read all SSIS:Property children into a lookup
        props = {}
        for prop in props_elem.findall(f"{{{_SSIS_NS}}}Property"):
            prop_name = prop.get(f"{{{_SSIS_NS}}}Name", "")
            prop_value = prop.text or ""
            props[prop_name] = prop_value.strip()

        param_dict: dict[str, object] = {
            "name": param_name,
            "data_type": props.get("DataType", ""),
            "sensitive": props.get("Sensitive", "0") == "1",
            "required": props.get("Required", "0") == "1",
            "include_in_debug_dump": props.get("IncludeInDebugDump", "0") == "1",
        }

        # Value is only present for non-sensitive parameters
        if not param_dict["sensitive"] and "Value" in props:
            param_dict["value"] = props["Value"]

        parameters.append(param_dict)

    return parameters


def _extract_package_info(root: ET.Element) -> list[dict]:
    """Extract PackageInfo section from the deployment info.

    Navigation path:
    DeploymentModelSpecificContent > Manifest > SSIS:Project >
    SSIS:DeploymentInfo > SSIS:PackageInfo > SSIS:PackageMetaData

    Each package metadata contains properties and optional parameters.

    Args:
        root: The root XML element.

    Returns:
        List of package info dicts.
    """
    # Navigate to PackageInfo
    deploy_content = root.find("DeploymentModelSpecificContent")
    if deploy_content is None:
        return []

    manifest_elem = deploy_content.find("Manifest")
    if manifest_elem is None:
        return []

    project_elem = manifest_elem.find(f"{{{_SSIS_NS}}}Project")
    if project_elem is None:
        return []

    deployment_info = project_elem.find(f"{{{_SSIS_NS}}}DeploymentInfo")
    if deployment_info is None:
        return []

    pkg_info_elem = deployment_info.find(f"{{{_SSIS_NS}}}PackageInfo")
    if pkg_info_elem is None:
        return []

    packages = []
    for meta_elem in pkg_info_elem.findall(f"{{{_SSIS_NS}}}PackageMetaData"):
        pkg_name = meta_elem.get(f"{{{_SSIS_NS}}}Name", "")

        # Extract properties
        properties = _extract_package_metadata_properties(meta_elem)

        # Extract package-level parameters (same structure as connection parameters)
        params_elem = meta_elem.find(f"{{{_SSIS_NS}}}Parameters")
        parameters = _extract_parameters(params_elem) if params_elem is not None else []

        packages.append(
            {
                "name": pkg_name,
                "properties": properties,
                "parameters": parameters,
            }
        )

    return packages


def _extract_package_metadata_properties(meta_elem: ET.Element) -> dict:
    """Extract properties from a PackageMetaData element.

    Args:
        meta_elem: The SSIS:PackageMetaData element.

    Returns:
        Dict mapping property names (snake_case) to their values.
    """
    properties_elem = meta_elem.find(f"{{{_SSIS_NS}}}Properties")
    if properties_elem is None:
        return {}

    # Map SSIS property names to output key names
    property_map = {
        "ID": "id",
        "Name": "name",
        "VersionMajor": "version_major",
        "VersionMinor": "version_minor",
        "VersionBuild": "version_build",
        "VersionComments": "version_comments",
        "VersionGUID": "version_guid",
        "PackageFormatVersion": "package_format_version",
        "Description": "description",
        "ProtectionLevel": "protection_level",
    }

    result = {}
    for prop_elem in properties_elem.findall(f"{{{_SSIS_NS}}}Property"):
        prop_name = prop_elem.get(f"{{{_SSIS_NS}}}Name", "")
        if prop_name in property_map:
            value = prop_elem.text or ""
            result[property_map[prop_name]] = value.strip()

    return result
