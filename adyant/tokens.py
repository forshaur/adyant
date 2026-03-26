import re
import json
from pathlib import Path

TYPES: dict[str, re.Pattern] = {
    ":uuid:":    re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I),
    ":hash:":    re.compile(r'^[0-9a-f]{32,}$', re.I),
    ":hex:":     re.compile(r'^[0-9a-f]{7,31}$', re.I),
    ":version:": re.compile(r'^v?\d+(\.\d+){1,3}$'),
    ":date:":    re.compile(r'^\d{4}[-/]\d{2}([-/]\d{2})?$'),
    ":year:":    re.compile(r'^(19|20)\d{2}$'),
    ":num:":     re.compile(r'^\d+$'),
}

def _load_kw(path: str = "keywords.json") -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return set(data)
    if isinstance(data, dict):
        out = []
        for v in data.values():
            if isinstance(v, list):
                out.extend(v)
        return set(out)
    return set()

KEYWORDS: set[str] = _load_kw()

LANGUAGES: set[str] = {
    "aa", "ab", "ae", "af", "ak", "am", "an", "ar", "ar-ae", "ar-bh",
    "ar-dz", "ar-eg", "ar-iq", "ar-jo", "ar-kw", "ar-lb", "ar-ly", "ar-ma",
    "ar-om", "ar-qa", "ar-sa", "ar-sy", "ar-tn", "ar-ye", "as", "av",
    "ay", "az", "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br",
    "bs", "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy", "da",
    "de", "de-at", "de-ch", "de-de", "de-li", "de-lu", "div", "dv", "dz",
    "ee", "el", "en", "en-au", "en-bz", "en-ca", "en-cb", "en-gb", "en-ie",
    "en-jm", "en-nz", "en-ph", "en-tt", "en-us", "en-za", "en-zw", "eo",
    "es", "es-ar", "es-bo", "es-cl", "es-co", "es-cr", "es-do", "es-ec",
    "es-es", "es-gt", "es-hn", "es-mx", "es-ni", "es-pa", "es-pe", "es-pr",
    "es-py", "es-sv", "es-us", "es-uy", "es-ve", "et", "eu", "fa", "ff",
    "fi", "fj", "fo", "fr", "fr-be", "fr-ca", "fr-ch", "fr-fr", "fr-lu",
    "fr-mc", "fy", "ga", "gd", "gl", "gn", "gu", "gv", "ha", "he", "hi",
    "ho", "hr", "hr-ba", "hr-hr", "ht", "hu", "hy", "hz", "ia", "id",
    "ie", "ig", "ii", "ik", "in", "io", "is", "it", "it-ch", "it-it",
    "iu", "iw", "ja", "ji", "jv", "jw", "ka", "kg", "ki", "kj", "kk",
    "kl", "km", "kn", "ko", "kok", "kr", "ks", "ku", "kv", "kw", "ky",
    "kz", "la", "lb", "lg", "li", "ln", "lo", "ls", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mo", "mr", "ms", "ms-bn", "ms-my",
    "mt", "my", "na", "nb", "nd", "ne", "ng", "nl", "nl-be", "nl-nl",
    "nn", "no", "nr", "ns", "nv", "ny", "oc", "oj", "om", "or", "os",
    "pa", "pi", "pl", "ps", "pt", "pt-br", "pt-pt", "qu", "qu-bo", "qu-ec",
    "qu-pe", "rm", "rn", "ro", "ru", "rw", "sa", "sb", "sc", "sd", "se",
    "se-fi", "se-no", "se-se", "sg", "sh", "si", "sk", "sl", "sm", "sn",
    "so", "sq", "sr", "sr-ba", "sr-sp", "ss", "st", "su", "sv", "sv-fi",
    "sv-se", "sw", "sx", "syr", "ta", "te", "tg", "th", "ti", "tk", "tl",
    "tn", "to", "tr", "ts", "tt", "tw", "ty", "ug", "uk", "ur", "us",
    "uz", "ve", "vi", "vo", "wa", "wo", "xh", "yi", "yo", "za", "zh",
    "zh-cn", "zh-hk", "zh-mo", "zh-sg", "zh-tw", "zu"
}

# Extensions stripped from path segments before typing.
# Covers server-side page extensions (original set) plus legacy/enterprise
# extensions that were missing: .cgi, .aspx, .do, .action, .cfm, .pl, .py
_EXT_RE = re.compile(
    r'\.(html?|php|asp[x]?|jsp|json|xml|txt|csv|cgi|do|action|cfm|pl|py)$',
    re.I,
)

# Static asset segments — segments whose *original* form (before extension
# stripping) looks like a deliverable file rather than a routable path node.
# These are filtered out of the token stream entirely at training time so
# they never enter the transition table.
# Covers: stylesheets, scripts (including minified/vendor), images, fonts,
# manifests, source-maps, web-assembly, and common build artefacts.
_ASSET_RE = re.compile(
    r'\.(css|js|mjs|cjs|map|ts|jsx|tsx'          # scripts / modules
    r'|png|jpe?g|gif|webp|svg|ico|bmp|avif'       # images
    r'|woff2?|ttf|otf|eot'                         # fonts
    r'|pdf|zip|tar|gz|bz2|xz|7z|rar'              # binary downloads
    r'|mp4|webm|ogg|mp3|wav|flac'                  # media
    r'|wasm|br)$',                                 # wasm / brotli pre-compressed
    re.I,
)

# Compound-extension sentinel: after the primary extension is stripped by
# _EXT_RE, a segment like "jquery.min" still has a dot-component that signals
# it is a static asset name, not a path keyword.  Catch the most common ones.
_COMPOUND_ASSET_RE = re.compile(r'\.(min|bundle|chunk|vendor|prod|dev)$', re.I)

_HASH_NAMES = {32: "md5", 40: "sha1", 56: "sha224", 64: "sha256", 96: "sha384", 128: "sha512"}


def _bin(tok: str, flat: str) -> str:
    if flat == ":num:":   return f":num:{len(tok)}:"
    if flat == ":hex:":   return f":hex:{len(tok)}:"
    if flat == ":hash:":
        name = _HASH_NAMES.get(len(tok), str(len(tok)))
        return f":hash:{name}:"
    return flat


def _digit_ratio(tok: str) -> float:
    return sum(1 for c in tok if c.isdigit()) / len(tok)


def label(tok: str) -> str:
    if tok in KEYWORDS: return tok
    if tok in LANGUAGES: return ":lang:"

    for tag, pat in TYPES.items():
        if tag == ":hex:":
            if pat.match(tok) and _digit_ratio(tok) >= 0.20:
                return ":hex:"
            continue
        if pat.match(tok):
            return tag

    if re.search(r"[-_]", tok) and len(tok) > 4:
        return ":word:"

    return tok


def label_pair(tok: str) -> tuple[str, str]:
    flat = label(tok)
    return flat, _bin(tok, flat)


def _is_asset(raw_seg: str) -> bool:
    """
    True if this path segment is a static asset filename that should never
    enter the transition table.

    Checked on the *raw* segment (before extension stripping) so that
    "main.css" and "jquery.min.js" are caught before _EXT_RE runs.
    Also checked on the post-strip form to catch compound names like
    "jquery.min" that survive the primary extension strip.
    """
    if _ASSET_RE.search(raw_seg):
        return True
    # After primary extension strip, check for compound suffixes (.min, .bundle …)
    stripped = _EXT_RE.sub("", raw_seg)
    if stripped != raw_seg and _COMPOUND_ASSET_RE.search(stripped):
        return True
    return False


def split(path: str, abstract: bool = True) -> list[str]:
    path = path.split("?")[0].split("#")[0]
    out  = []
    for seg in path.split("/"):
        seg = seg.lower().strip()
        if not seg:
            continue
        if _is_asset(seg):          # drop static asset filenames entirely
            continue
        seg = _EXT_RE.sub("", seg)
        if not seg:
            continue
        out.append(label(seg) if abstract else seg)
    return out


def split_pairs(path: str) -> list[tuple[str, str]]:
    path = path.split("?")[0].split("#")[0]
    out  = []
    for seg in path.split("/"):
        seg = seg.lower().strip()
        if not seg:
            continue
        if _is_asset(seg):          # drop static asset filenames entirely
            continue
        seg = _EXT_RE.sub("", seg)
        if not seg:
            continue
        out.append(label_pair(seg))
    return out
