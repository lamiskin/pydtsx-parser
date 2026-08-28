# Real-world SSIS fixtures

Genuine SSIS packages authored by Visual Studio and published in public
repositories under the MIT licence. They complement the hand-written XML used
elsewhere in the suite, which cannot reproduce real attribute ordering,
third-party component class IDs, or SSIS 2012 project layout.

## Provenance

| Directory | Upstream | Licence | Retrieved |
|---|---|---|---|
| `u2_toolkit/` | [RocketSoftware/multivalue-lab](https://github.com/RocketSoftware/multivalue-lab) — `U2/Demos/U2-Toolkit/` | MIT | 2026-07-27 |
| `ssis_examples/` | [7045kHz/dtsx](https://github.com/7045kHz/dtsx) — `SSIS_EXAMPLES/` | MIT | 2026-07-27 |

Both upstream projects are MIT licensed; their copyright notices remain with the
respective owners. The files are redistributed here under those terms solely as
parser test data.

## Sanitisation

These files were authored inside other organisations and originally embedded
their identifiers. Every occurrence was rewritten before committing, so the
fixtures are **not** byte-for-byte identical to upstream:

| What it was | Replacement |
|---|---|
| Domain-qualified user accounts (two forms, two domains) | `EXAMPLE\etluser` |
| The same user name in `C:\Users\…` profile paths | `etluser` |
| Four workstation / VM host names | `BUILDHOST01`–`BUILDHOST04` |
| An internal RFC 1918 address | `192.0.2.10` (RFC 5737 documentation range) |
| An Azure SQL server host name | `example-sql.database.windows.net` |
| A database named after its author | `ExampleDB` |
| A connection-string login | `etluser` |
| A personal repository folder name in a `C:\Users\…\source\repos\…` path (`Expressions.dtsx`) | `ExampleRepo` |
| A second, distinct personal repository folder name in the same path shape, in a sibling fixture (`ConfigTables.dtsx`) | `SampleRepo` |

The upstream values are deliberately **not** listed here. Naming them would
republish, in one convenient table, the very identifiers the substitution
removed — a user account, four hosts, an internal address and a database
endpoint, attributable to a named person at a named company. They are held as
hashes in `tests/scrubbed_guard.py` instead; that module documents what the
hashing does and does not achieve.

> **Why the last row exists.** The first pass rewrote the user name component of
> this path (`etluser`) but missed the repository-folder component sitting one
> level deeper in the same string — a local clone name, distinct from the
> credited upstream repository, that named nothing in the substitution table
> above and so nothing hashed it. It was also 9 characters long, a length
> `scrubbed_guard.py`'s window check did not test, so an identifier that *had*
> been hashed would still have passed unnoticed. Both gaps are fixed: the value
> is hashed below, and the window lengths now include 9.

> **Why the second-to-last row exists.** A later audit found the same
> repository-folder pattern once more, in `ConfigTables.dtsx`, which the prior
> two passes had not checked — the earlier fix covered `Expressions.dtsx` only.
> It is a distinct local clone name, unrelated to `ExampleRepo` above, now
> replaced and hashed the same way.

Substitutions were length-preserving in structure only — XML shape, element and
attribute counts, and all parse results are unchanged. `test_real_world.py`
asserts the parsed structure still matches.

Two guards run over the fixtures. `test_fixtures_contain_no_unscrubbed_identifiers`
hashes candidate windows out of each fixture and compares them against the stored
digests, so a refresh from upstream that skips this step fails the build.
`test_fixtures_contain_no_identifier_shaped_strings` asserts on the *shape* of a
leak — UNC servers, e-mail addresses, OneDrive tenants, RFC 1918 addresses, and
Windows profile paths under an unexpected user — so an identifier nobody has
thought of yet fails the first time it appears, rather than waiting to be added
to a list. The named list is retrospective by nature: three of the entries above
survived the first pass precisely because nobody had written them down.

Package/component GUIDs were deliberately **left intact**: SSIS identifies
component classes by GUID, so rewriting them would stop the fixtures
representing real packages.

## Refreshing

Re-download from the upstream URLs above, re-apply the substitution table, and
re-run `pytest tests/test_real_world.py`. Do not commit upstream files directly.

Because the upstream values are not written down here, recovering them means
opening the upstream files and reading the identifiers out — which is the
sanitisation step anyway. If that pass turns up an identifier the guard does not
yet know about, add it by hashing its lowercased form and extending both
`_DIGESTS` and `_WINDOW_LENGTHS` in `tests/scrubbed_guard.py`:

```bash
python3 -c 'import hashlib,sys; v=sys.argv[1].lower(); print(hashlib.sha256(v.encode()).hexdigest(), len(v))' 'VALUE'
```
