"""Custom exception types for the SSIS Parser."""


class SSISParseError(Exception):
    """Base exception for parse failures.

    All SSIS parser errors carry the file path that triggered the error
    and a human-readable reason string.
    """

    def __init__(self, file_path: str, reason: str) -> None:
        self.file_path = file_path
        self.reason = reason
        super().__init__(f"{file_path}: {reason}")


class FileNotFoundError(SSISParseError):
    """File does not exist or is not readable."""

    def __init__(
        self, file_path: str, reason: str = "File not found or not readable"
    ) -> None:
        super().__init__(file_path, reason)


class MalformedXMLError(SSISParseError):
    """XML could not be parsed."""

    def __init__(self, file_path: str, reason: str = "Malformed XML") -> None:
        super().__init__(file_path, reason)


class ExtractionError(SSISParseError):
    """Required element or attribute missing during extraction."""

    def __init__(self, file_path: str, reason: str = "Extraction failed") -> None:
        super().__init__(file_path, reason)
