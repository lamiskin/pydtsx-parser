"""Output envelope builder for the SSIS Parser.

Wraps parsed content with metadata including format version, parser version,
source file information, data type map, and redaction summary.
"""

import os
import platform
from datetime import UTC, datetime
from pathlib import Path

from pydtsx_parser import __version__
from pydtsx_parser.constants import DATA_TYPE_MAP

# Version of the output envelope schema. Bump only when the envelope shape
# changes in a way consumers must react to — this is independent of the
# package version.
FORMAT_VERSION = "1.0.0"

# Version of the parser that produced the output. Tracks the package version
# so automated release bumps stay reflected in the output.
PARSER_VERSION = __version__

# Valid file_type values
VALID_FILE_TYPES = {
    "dtsx_package",
    "dtproj_project",
    "conmgr_connection",
    "params_parameters",
}


def build_envelope(
    content: dict,
    source_path: str,
    file_type: str,
    redaction_count: int,
) -> dict:
    """Wrap parsed content with format_version, parser_version,
    source_file_path, file_type, parsed_at, source_file_metadata,
    data_type_map, and redaction_summary.

    Args:
        content: The parsed file content dictionary.
        source_path: Path to the source file that was parsed.
        file_type: One of "dtsx_package", "dtproj_project",
                   "conmgr_connection", "params_parameters".
        redaction_count: Number of sensitive values that were redacted.

    Returns:
        A dictionary containing the full output envelope with metadata
        wrapping the parsed content.
    """
    absolute_path = str(Path(source_path).resolve())
    parsed_at = datetime.now(UTC).astimezone().isoformat()

    envelope = {
        "format_version": FORMAT_VERSION,
        "parser_version": PARSER_VERSION,
        "source_file_path": absolute_path,
        "file_type": file_type,
        "parsed_at": parsed_at,
        "source_file_metadata": collect_source_file_metadata(source_path),
        "data_type_map": DATA_TYPE_MAP,
        "redaction_summary": {"total_redacted": redaction_count},
        "content": content,
    }

    return envelope


def collect_source_file_metadata(file_path: str) -> dict:
    """Collect filesystem metadata for the source file.

    Returns dict with keys: file_name, file_size_bytes,
    last_modified (ISO 8601), created (ISO 8601), owner.
    Uses os.stat() and platform-specific owner resolution.

    Args:
        file_path: Path to the source file.

    Returns:
        A dictionary with filesystem metadata. The owner field is null
        if the filesystem owner cannot be determined.
    """
    path = Path(file_path)
    stat_result = os.stat(file_path)

    file_name = path.name
    file_size_bytes = stat_result.st_size

    # Convert modification time to ISO 8601 with timezone
    last_modified = (
        datetime.fromtimestamp(stat_result.st_mtime, tz=UTC).astimezone().isoformat()
    )

    # Convert creation time to ISO 8601 with timezone
    # On Windows, st_ctime is creation time; on Unix it's metadata change time
    created = (
        datetime.fromtimestamp(stat_result.st_ctime, tz=UTC).astimezone().isoformat()
    )

    owner = _resolve_file_owner(file_path)

    return {
        "file_name": file_name,
        "file_size_bytes": file_size_bytes,
        "last_modified": last_modified,
        "created": created,
        "owner": owner,
    }


def _resolve_file_owner(file_path: str) -> str | None:
    """Resolve the filesystem owner of a file.

    Tries Windows security APIs first, then falls back to Unix pwd module.
    Returns None if the owner cannot be determined.

    Args:
        file_path: Path to the file.

    Returns:
        The owner as a string (e.g., "DOMAIN\\username") or None.
    """
    if platform.system() == "Windows":
        return _resolve_windows_owner(file_path)
    else:
        return _resolve_unix_owner(file_path)


def _resolve_windows_owner(file_path: str) -> str | None:
    """Resolve file owner on Windows using win32 security APIs.

    Returns None if the owner cannot be determined.
    """
    try:
        import win32security

        security_descriptor = win32security.GetFileSecurity(
            file_path, win32security.OWNER_SECURITY_INFORMATION
        )
        owner_sid = security_descriptor.GetSecurityDescriptorOwner()
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        if domain:
            return f"{domain}\\{name}"
        return name
    except Exception:
        return None


def _resolve_unix_owner(file_path: str) -> str | None:
    """Resolve file owner on Unix/Linux using pwd module.

    Returns None if the owner cannot be determined.
    """
    try:
        import pwd

        stat_result = os.stat(file_path)
        pw_entry = pwd.getpwuid(stat_result.st_uid)
        return pw_entry.pw_name
    except Exception:
        return None
