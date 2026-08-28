# Security Policy

## Supported versions

The latest released version on PyPI receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities **privately** using GitHub's
[private vulnerability reporting](https://github.com/lamiskin/pydtsx-parser/security/advisories/new).
Do not open a public issue.

You can expect an initial response within a few days.

**Do not attach real SSIS packages, extracts, or production data** to a report.
Reduce your case to a minimal synthetic reproducer with server names, paths, and
credentials replaced.

## Security model, and what this tool does not guarantee

`pydtsx-parser` reads XML files and produces JSON. It executes no SSIS logic,
opens no database connections, and resolves no external entities.

It performs **best-effort credential redaction**: fields matching sensitive
patterns (`password`, `pwd`, `orapassword`, …) and password keys inside
connection strings are replaced with a placeholder, and the count is reported in
`redaction_summary`.

Treat that as a convenience, not a security boundary:

- Redaction targets credentials. It does **not** remove internal server names,
  UNC paths, database or schema names, or domain usernames — all of which SSIS
  packages routinely contain.
- Parser output additionally includes the source file's absolute path and its
  filesystem owner.
- Custom or unusual connection string formats may not match the redaction
  patterns.

**Review parser output before sharing it** outside your organisation, attaching
it to an issue, or feeding it to an external service. If you find a case where a
credential survives redaction, please report it privately as a vulnerability.
