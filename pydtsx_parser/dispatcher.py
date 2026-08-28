"""File dispatcher for the SSIS Parser.

Routes files to the correct parser by extension, handles directory scanning
for recursive discovery of supported SSIS files, and produces combined
project-level output when given a directory.

Supported file types:
- .dtsx  → DTSX package parser
- .dtproj → DTPROJ project parser
- .conmgr → Connection manager parser
- .params → Parameters parser
"""

import os
import sys
from pathlib import Path

from pydtsx_parser.envelope import build_envelope
from pydtsx_parser.errors import SSISParseError
from pydtsx_parser.parsers.conmgr import parse_conmgr
from pydtsx_parser.parsers.dtproj import parse_dtproj
from pydtsx_parser.parsers.dtsx import parse_dtsx
from pydtsx_parser.parsers.params import parse_params
from pydtsx_parser.redaction import redact

# Supported file extensions for SSIS parsing
SUPPORTED_EXTENSIONS = {".dtsx", ".dtproj", ".conmgr", ".params"}

# Mapping of file extension to file_type enum value
_EXTENSION_TO_FILE_TYPE = {
    ".dtsx": "dtsx_package",
    ".dtproj": "dtproj_project",
    ".conmgr": "conmgr_connection",
    ".params": "params_parameters",
}

# Mapping of file extension to parser function
_EXTENSION_TO_PARSER = {
    ".dtsx": parse_dtsx,
    ".dtproj": parse_dtproj,
    ".conmgr": parse_conmgr,
    ".params": parse_params,
}


def dispatch(path: str, pretty: bool = False) -> dict:
    """Parse a single file or directory and return the result dict.

    For a single file:
        - Detects file type from extension
        - Calls the appropriate parser
        - Applies redaction
        - Wraps in output envelope with metadata

    For a directory:
        - Recursively scans for supported SSIS files
        - Parses each file
        - Produces combined project-level output grouping packages,
          connection managers, and parameters with cross-references
          by ObjectName

    Args:
        path: File or directory path to parse.
        pretty: Whether to pretty-print JSON (passed through for
                downstream consumers; does not affect dict output).

    Returns:
        The parsed result dictionary (envelope for single files,
        combined project structure for directories).

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If a single file has an unsupported extension.
    """
    if not path:
        raise FileNotFoundError(path or "", "Path is empty or None")

    resolved = Path(path).resolve()

    if not resolved.exists():
        raise FileNotFoundError(str(resolved), f"Path does not exist: {resolved}")

    if resolved.is_dir():
        return _dispatch_directory(str(resolved))
    else:
        return _dispatch_file(str(resolved))


def scan_directory(dir_path: str) -> list[str]:
    """Recursively find all supported SSIS files in a directory tree.

    Walks the directory tree and collects files with extensions matching
    SUPPORTED_EXTENSIONS. Results are sorted for deterministic output.

    Args:
        dir_path: Path to the directory to scan.

    Returns:
        Sorted list of absolute file paths for all supported SSIS files.
    """
    found_files = []
    resolved = Path(dir_path).resolve()

    for root, _dirs, files in os.walk(str(resolved)):
        for filename in files:
            ext = Path(filename).suffix.lower()
            if ext in SUPPORTED_EXTENSIONS:
                found_files.append(str(Path(root) / filename))

    found_files.sort()
    return found_files


def detect_file_type(file_path: str) -> str:
    """Map file extension to file_type enum value.

    Args:
        file_path: Path to the file.

    Returns:
        One of: "dtsx_package", "dtproj_project", "conmgr_connection",
        "params_parameters".

    Raises:
        ValueError: If the file extension is not supported.
    """
    ext = Path(file_path).suffix.lower()
    if ext not in _EXTENSION_TO_FILE_TYPE:
        raise ValueError(
            f"Unsupported file extension '{ext}' for file: {file_path}. "
            f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return _EXTENSION_TO_FILE_TYPE[ext]


def _dispatch_file(file_path: str) -> dict:
    """Parse a single file: detect type, parse, redact, wrap in envelope.

    Args:
        file_path: Absolute path to the file.

    Returns:
        Output envelope dict with parsed content.

    Raises:
        ValueError: If file extension is not supported.
    """
    file_type = detect_file_type(file_path)
    ext = Path(file_path).suffix.lower()
    parser = _EXTENSION_TO_PARSER[ext]

    # Call the appropriate parser
    content = parser(file_path)

    # Apply redaction
    redacted_content, redaction_count = redact(content)

    # Wrap in output envelope
    envelope = build_envelope(
        content=redacted_content,
        source_path=file_path,
        file_type=file_type,
        redaction_count=redaction_count,
    )

    return envelope


def _dispatch_directory(dir_path: str) -> dict:
    """Parse all supported files in a directory and produce combined output.

    Produces a project-level structure grouping:
    - packages (.dtsx files)
    - connection_managers (.conmgr files)
    - parameters (.params files)
    - projects (.dtproj files)

    Cross-references are established by ObjectName where available.

    Args:
        dir_path: Absolute path to the directory.

    Returns:
        Combined project-level output dict.
    """
    files = scan_directory(dir_path)

    packages = []
    connection_managers = []
    parameters = []
    projects = []
    errors = []

    for file_path in files:
        ext = Path(file_path).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            # Skip unsupported files with a warning
            print(
                f"Warning: Skipping unsupported file type: {file_path}",
                file=sys.stderr,
            )
            continue

        try:
            file_type = detect_file_type(file_path)
            parser = _EXTENSION_TO_PARSER[ext]
            content = parser(file_path)

            # Check if parser returned an error dict
            if isinstance(content, dict) and content.get("error"):
                errors.append(
                    {
                        "file_path": file_path,
                        "file_type": file_type,
                        "error": content,
                    }
                )
                continue

            # Apply redaction to content
            redacted_content, redaction_count = redact(content)

            entry = {
                "file_path": file_path,
                "file_type": file_type,
                "file_name": Path(file_path).name,
                "redaction_count": redaction_count,
                "content": redacted_content,
            }

            # Add ObjectName cross-reference where available
            object_name = _extract_object_name(redacted_content, ext)
            if object_name:
                entry["object_name"] = object_name

            # Group by file type
            if ext == ".dtsx":
                packages.append(entry)
            elif ext == ".conmgr":
                connection_managers.append(entry)
            elif ext == ".params":
                parameters.append(entry)
            elif ext == ".dtproj":
                projects.append(entry)

        except SSISParseError as e:
            errors.append(
                {
                    "file_path": file_path,
                    "file_type": _EXTENSION_TO_FILE_TYPE.get(ext, "unknown"),
                    "error": {
                        "error": True,
                        "file_path": file_path,
                        "error_type": type(e).__name__.lower(),
                        "message": str(e),
                    },
                }
            )
        except Exception as e:
            errors.append(
                {
                    "file_path": file_path,
                    "file_type": _EXTENSION_TO_FILE_TYPE.get(ext, "unknown"),
                    "error": {
                        "error": True,
                        "file_path": file_path,
                        "error_type": "unexpected_error",
                        "message": str(e),
                    },
                }
            )

    # Build cross-reference index by ObjectName
    cross_references = _build_cross_references(
        packages, connection_managers, parameters
    )

    return {
        "directory_path": dir_path,
        "file_type": "project_directory",
        "summary": {
            "total_files": len(files),
            "packages": len(packages),
            "connection_managers": len(connection_managers),
            "parameters": len(parameters),
            "projects": len(projects),
            "errors": len(errors),
        },
        "packages": packages,
        "connection_managers": connection_managers,
        "parameters": parameters,
        "projects": projects,
        "cross_references": cross_references,
        "errors": errors,
    }


def _extract_object_name(content: dict, ext: str) -> str | None:
    """Extract the ObjectName from parsed content for cross-referencing.

    Args:
        content: The parsed (and redacted) content dict.
        ext: The file extension.

    Returns:
        The ObjectName string if found, or None.
    """
    if ext == ".dtsx":
        # DTSX packages have object_name in package_attributes
        pkg_attrs = content.get("package_attributes", {})
        return pkg_attrs.get("object_name")
    elif ext == ".conmgr":
        # Connection managers have object_name in the connection_manager dict
        conn_mgr = content.get("connection_manager", {})
        return conn_mgr.get("object_name")
    elif ext == ".dtproj":
        # Project files: use the project name from manifest
        manifest = content.get("manifest", {})
        project_props = manifest.get("project_properties", {})
        return project_props.get("name")
    elif ext == ".params":
        # Params files don't typically have an object name
        return None
    return None


def _build_cross_references(
    packages: list[dict],
    connection_managers: list[dict],
    parameters: list[dict],
) -> dict:
    """Build cross-reference index mapping ObjectNames across file types.

    Creates a lookup that shows which connection managers and parameters
    are referenced by which packages.

    Args:
        packages: List of parsed package entries.
        connection_managers: List of parsed connection manager entries.
        parameters: List of parsed parameter entries.

    Returns:
        Dict with connection_manager_index and parameter_index.
    """
    # Index connection managers by their ObjectName
    conn_mgr_index = {}
    for cm in connection_managers:
        obj_name = cm.get("object_name")
        if obj_name:
            conn_mgr_index[obj_name] = {
                "file_path": cm.get("file_path"),
                "file_name": cm.get("file_name"),
            }

    # Index which packages reference which connection managers
    package_connections = {}
    for pkg in packages:
        pkg_name = pkg.get("object_name", pkg.get("file_name", ""))
        content = pkg.get("content", {})
        pkg_conn_mgrs = content.get("connection_managers", [])
        referenced_names = []
        for conn in pkg_conn_mgrs:
            conn_name = conn.get("object_name")
            if conn_name:
                referenced_names.append(conn_name)
        if referenced_names:
            package_connections[pkg_name] = referenced_names

    return {
        "connection_manager_index": conn_mgr_index,
        "package_connection_references": package_connections,
    }
