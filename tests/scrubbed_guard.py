"""Hashed guard for the upstream identifiers scrubbed from the real-world fixtures.

The fixtures under ``tests/fixtures/real_world/`` were authored inside other
organisations and originally embedded their identifiers — a user name, several
workstation names, an internal address, a database host. Those were rewritten
before committing, and a guard asserts they never come back, which a refresh
from upstream would otherwise reintroduce silently.

Holding that guard's list as plaintext, however, republishes in this repository
exactly the values the sanitisation removed, gathered into one convenient place.
So the identifiers are stored here as SHA-256 digests of their lowercased form,
and the guard hashes candidate windows out of the fixture text to compare.

**This is disclosure control, not secrecy.** The identifiers are short and
guessable, and anyone who suspects a particular value can confirm it by hashing
it. What the digests achieve is that the values are no longer *readable* here:
not indexed by search engines, not harvestable from a clone, and not presented
as an assembled profile. That is the whole of the intent.

Regenerating: the plaintext list is not kept in this repository. To add an
identifier, hash its lowercased form with ``sha256`` and add the digest plus its
length below; see ``tests/fixtures/real_world/README.md`` for the procedure.
"""

import hashlib

# SHA-256 of each scrubbed identifier, lowercased. See the module docstring.
_DIGESTS = frozenset(
    {
        "1c49bfb8ff1a7b226803e7f49a89d6f423973c101bcf9841681b5e42a3129566",
        "37d723aa09a04f367d1c7f86144b207f4f966f635aabb4cb81ff099fb3fd8a62",
        "42f250827b3bf5c48b99e7b1894fe59269a8e363172a7fb7d3d6e07fe05faf66",
        "5d0302db67d6641e7f97df9f18742d303c4fb749b4d26906a6f5b9ee771e577b",
        "61c8129e48002e0fd885ef69fde34f75af2c960948ed068db77daa94b48072dd",
        "8b07ef6a0bcd1abbde5c5250fe87f261743a7f574c99afd24fd8592770122907",
        "b0153214a4150820d32707a8d623e68dd52f61e6b759f8de008469c9cd131cb2",
        "c6e4d2b4eef9a9d3bc458d23b0994bd6c99e93d6c3cb072cd362de8d27687e28",
        "d9b4808896caf9b944d09344e067190c90eb44c81a86b570d1af05e221978034",
        "effa83749a43acc5da135823abf3776074ab2bd82a227228ba912fbe73570f2d",
        "b5a2b78291fcb1b1e62d7f614d67a76694b1a74e2cd2e1d5c3b4aea5a0356667",
    }
)

# A digest can only be checked against a window of the right size, so lengths
# outside this range are invisible to the guard by construction. Two identifiers
# have already slipped through this way — hashed but at a length the guard never
# tested — so this is a contiguous range wide enough for any realistic single
# token (username, hostname, path segment) rather than the exact set of lengths
# seen so far, which is exactly what proved too narrow twice.
_WINDOW_LENGTHS = tuple(range(3, 33))


def find_scrubbed(text: str) -> tuple[int, str] | None:
    """Return ``(offset, digest)`` of the first scrubbed identifier in *text*.

    Returns ``None`` if the text is clean. The identifier itself is deliberately
    not returned — the caller reports the offset, which is enough to find it in
    a local working copy without printing it into CI logs.

    Windows are anchored to token starts (the beginning of the text, or any
    position following a non-alphanumeric character), which is where every known
    identifier begins: ``rajanVM`` and ``DEN-L-RK01`` both extend a token rather
    than sitting inside one, and profile paths break on the separator. An
    identifier buried mid-token would be missed here; the shape patterns in
    ``test_real_world.py`` are the backstop for anything this list cannot name.
    """
    haystack = text.lower()
    limit = len(haystack)
    for index in range(limit):
        if index and haystack[index - 1].isalnum():
            continue
        for length in _WINDOW_LENGTHS:
            if index + length > limit:
                break
            window = haystack[index : index + length]
            digest = hashlib.sha256(window.encode()).hexdigest()
            if digest in _DIGESTS:
                return index, digest
    return None
