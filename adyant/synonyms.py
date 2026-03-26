"""
synonyms.py — Merge semantically equivalent URL tokens.

Problem: three different codebases might use /users/delete, /users/remove,
and /users/destroy. To a pure token-counter these are three separate words
with split probability. We collapse them all to one word so counts accumulate.
"""

# Each group contains words that mean the same thing in URL space.
# The canonical form is the alphabetically first word in the group.

GROUPS: list[set[str]] = [
    {"delete", "remove", "destroy", "drop"},
    {"create", "new", "add", "insert", "make"},
    {"update", "edit", "modify", "patch", "change"},
    {"list", "all", "index", "browse"},
    {"user", "users", "account", "accounts", "member", "members"},
    {"image", "images", "photo", "photos", "picture", "pictures", "img"},
    {"thumb", "thumbs", "thumbnail", "thumbnails"},
    {"docs", "documentation", "help", "guide", "guides"},
    {"login", "signin", "sign-in"},
    {"logout", "signout", "sign-out"},
    {"register", "signup", "sign-up", "join"},
    {"search", "query", "find", "lookup"},
    {"profile", "me", "self", "whoami"},
    {"dashboard", "home", "overview", "summary"},
    {"settings", "config", "configuration", "preferences", "prefs"},
    {"export", "download"},
    {"import", "upload"},
    {"callback", "webhook", "hook"},
    {"token", "tokens", "key", "keys", "secret"},
    {"report", "reports", "analytics", "stats", "statistics", "metrics"},
]

# Build fast lookup: word → canonical form
_MAP: dict[str, str] = {}
for group in GROUPS:
    canon = sorted(group)[0]
    for word in group:
        _MAP[word] = canon


def canon(tok: str) -> str:
    """Return the canonical synonym for a token, or the token itself."""
    return _MAP.get(tok, tok)
