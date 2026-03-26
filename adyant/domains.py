"""
domains.py — Detect the type of site a URL path belongs to.

Problem: a mixed training corpus (API sites + blogs + e-commerce) causes
token pollution. A  CMS word bleeds into API predictions because both
get abstracted to :word: and land in the same probability bucket.

Fix: cluster training URLs by site type. At generation time, detect what type
the seed is, and only use transitions from matching clusters.
"""

# Each profile is a set of keywords that signal a site type.
PROFILES: dict[str, set[str]] = {
    "api": {
        "api", "v1", "v2", "v3", "graphql", "rest", "rpc",
        "webhook", "webhooks", "callback", "token", "tokens",
        "oauth", "sso", "saml", "oidc", "endpoint",
    },
    "auth": {
        "login", "logout", "register", "signup", "signin",
        "password", "reset", "verify", "confirm", "auth",
        "oauth", "sso", "token", "refresh", "2fa", "mfa",
    },
    "cms": {
        "blog", "post", "posts", "page", "pages", "article",
        "category", "categories", "tag", "tags", "feed", "rss",
        "author", "archive", "comment", "comments",
    },
    "admin": {
        "admin", "dashboard", "report", "reports", "audit",
        "logs", "manage", "control", "panel", "console",
        "metrics", "analytics", "stats",
    },
    "media": {
        "gallery", "album", "photo", "photos", "image", "images",
        "thumb", "thumbs", "thumbnail", "upload", "media",
        "static", "assets", "cdn",
    },
    "shop": {
        "product", "products", "cart", "checkout", "order", "orders",
        "payment", "billing", "invoice", "subscription", "shop", "store",
    },
}


def scores(tokens: list[str]) -> dict[str, float]:
    """Score a list of tokens against every domain profile (0.0 – 1.0)."""
    raw: dict[str, float] = {}
    for name, words in PROFILES.items():
        hits = sum(1 for t in tokens if t in words)
        raw[name] = hits / max(len(tokens), 1)
    total = sum(raw.values()) or 1.0
    return {d: s / total for d, s in raw.items()}


def detect(tokens: list[str]) -> str | None:
    """Return the best-matching domain name, or None if nothing matches."""
    sc = scores(tokens)
    best = max(sc, key=sc.__getitem__)
    return best if sc[best] > 0.0 else None
