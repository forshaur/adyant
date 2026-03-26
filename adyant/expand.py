import random
import re

FALLBACKS: dict[str, list[str]] = {
    ":num:":         ["1", "2", "10", "42", "100"],
    ":uuid:":        ["550e8400-e29b-41d4-a716-446655440000"],
    ":hex:":         ["a1b2c3d", "deadbeef"],
    ":hash:md5:":    ["d41d8cd98f00b204e9800998ecf8427e"],
    ":hash:sha1:":   ["da39a3ee5e6b4b0d3255bfef95601890afd80709"],
    ":hash:sha256:": ["e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    ":version:":     ["v1", "v2"],
    ":date:":        ["2024-01-01", "2023-12-01"],
    ":year:":        ["2024", "2023"],
    ":lang:":        ["en", "en-us"],
    ":word:":        ["example", "test"],
}

_TAG = re.compile(r":[a-z0-9]+(?::[a-z0-9]+)?:")


class Expander:
    """
    Replaces typed placeholders with real values seen in training.
    Falls back to safe static defaults when no corpus examples exist.
    """

    def __init__(self, real_vals: dict | None = None):
        self.corpus = real_vals or {}

    def choices(self, tag: str) -> list:
        vals = self.corpus.get(tag, [])
        if vals:
            return vals
        base = re.match(r"(:[a-z]+:)", tag)
        if base:
            vals = self.corpus.get(base.group(1), [])
            if vals:
                return vals
        return FALLBACKS.get(tag, [tag])

    def expand(self, path: str) -> str:
        def sub(m):
            return random.choice(self.choices(m.group(0)))
        prev = None
        while prev != path:
            prev = path
            path = _TAG.sub(sub, path)
        return path

    def coverage_report(self) -> dict:
        all_tags = set(FALLBACKS) | set(self.corpus)
        return {t: len(self.corpus.get(t, [])) for t in sorted(all_tags)}


def expand(path: str) -> str:
    return Expander().expand(path)