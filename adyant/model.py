import json
import re
import math
from collections import defaultdict, Counter
from urllib.parse import urlparse

from .tokens  import split, split_pairs, TYPES, LANGUAGES
from .synonyms import canon
from .domains  import detect

START = "<ADI>"
END   = "<ANT>"

# filters for corpus keyword mining (mirrors clean.py logic)
_BAD  = re.compile(r"[^a-z0-9\-]")
_word = re.compile(r"[-_]")
_EXT  = re.compile(r"\.(html?|php|asp|jsp|json|xml|txt|csv)$")
_TYPE_PATS = list(TYPES.values())


def _is_keyword_candidate(tok: str) -> bool:
    """True if this token looks like a structural keyword, not an opaque value."""
    if not tok or len(tok) < 2 or len(tok) > 25:
        return False
    if _BAD.search(tok):
        return False
    if tok.isdigit():
        return False
    if tok in LANGUAGES:
        return False
    for pat in _TYPE_PATS:
        if pat.match(tok):
            return False
    if _word.search(tok) and len(tok) > 4:
        return False
    return True


class Model:
    def __init__(self, order: int = 3, discount: float = 0.75):
        self.order    = order
        self.discount = discount

        self.trans:    dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.cont:     dict[str, int]              = defaultdict(int)
        self.freq:     dict[str, int]              = defaultdict(int)
        self.ctx_site: dict[tuple, set[str]]       = defaultdict(set)

        self.vocab:     set[str]              = set()
        self.total:     int                   = 0
        self.real_vals: dict[str, list[str]]  = defaultdict(list)

        # discovered keywords — populated during train()
        self.learned_kw: set[str] = set()

    def train(self, urls: list[str],
              min_freq: int = 5,
              min_domains: int = 3) -> "Model":
        """
        Train on a list of URL strings.

        Before building the transition table, mines the corpus for
        structural keywords (tokens that appear across many domains
        with high frequency) and merges them into the KEYWORDS set
        so the tokeniser treats them as literals, not opaque values.

        min_freq    — minimum total appearances to be a keyword candidate
        min_domains — minimum distinct hostnames to be a keyword candidate
        """
        clean = [u.strip() for u in urls if u.strip()]

        # pass 1: mine keywords from corpus
        self._mine_keywords(clean, min_freq, min_domains)

        # pass 2: build transition table (tokeniser now knows learned keywords)
        for url in clean:
            self._add(url)

        print(f"Trained  urls={self.total}  contexts={len(self.trans)}"
              f"  vocab={len(self.vocab)}  learned keywords={len(self.learned_kw)}")
        return self

    def _mine_keywords(self, urls: list[str], min_freq: int, min_domains: int) -> None:
        """
        Scan the raw URL list, count token frequency and distinct hostnames,
        and add any token that passes both thresholds to KEYWORDS so the
        tokeniser treats it as a structural keyword going forward.
        """
        from .tokens import KEYWORDS

        freq:    Counter            = Counter()
        domains: defaultdict[str, set] = defaultdict(set)

        for url in urls:
            try:
                p    = urlparse(url if "://" in url else "https://" + url)
                host = p.netloc.lower().lstrip("www.")
                path = p.path
            except Exception:
                continue

            for seg in path.split("/"):
                seg = seg.lower().strip()
                if not seg:
                    continue
                seg = _EXT.sub("", seg)
                if not seg:
                    continue
                if _is_keyword_candidate(seg) and seg not in KEYWORDS:
                    freq[seg] += 1
                    domains[seg].add(host)

        for tok, count in freq.items():
            if count >= min_freq and len(domains[tok]) >= min_domains:
                KEYWORDS.add(tok)
                self.learned_kw.add(tok)

    def _add(self, url: str) -> None:
        parsed  = urlparse(url if "://" in url else "https://" + url)
        pairs   = split_pairs(parsed.path)
        if not pairs:
            return

        flat_toks = [canon(f) for f, _ in pairs]
        raw_toks  = split(parsed.path, abstract=False)

        for (_, bin_tag), raw in zip(pairs, raw_toks):
            if bin_tag.startswith(":") and bin_tag != raw:
                if raw not in self.real_vals[bin_tag]:
                    self.real_vals[bin_tag].append(raw)

        site = detect(flat_toks)
        self.total += 1
        self.vocab.update(flat_toks)

        seq = [START] * self.order + flat_toks + [END]

        for i in range(self.order, len(seq)):
            tok = seq[i]
            for w in range(1, self.order + 1):
                ctx = tuple(seq[i - w: i])
                self.trans[ctx][tok] += 1
                if site:
                    self.ctx_site[ctx].add(site)
            if tok not in (START, END):
                self.cont[tok] += 1
                self.freq[tok] += 1

    def next_probs(self, prefix: list[str], site: str | None = None, boost: float = 2.0) -> dict[str, float]:
        for w in range(min(self.order, len(prefix)), 0, -1):
            ctx = tuple(prefix[-w:])
            p   = self._kn(ctx, site, boost)
            if p:
                return p
        if self.vocab:
            v = 1.0 / len(self.vocab)
            return {t: v for t in self.vocab if t not in (START, END)}
        return {}

    def _kn(self, ctx: tuple, site: str | None, boost: float) -> dict[str, float]:
        raw = self.trans.get(ctx, {})
        if not raw and not self.cont:
            return {}

        sites = self.ctx_site.get(ctx, set())
        w: dict[str, float] = {}
        for tok, cnt in raw.items():
            if site and sites:
                wt = boost if site in sites else 1.0 / boost
            else:
                wt = 1.0
            w[tok] = cnt * wt

        total    = sum(w.values()) or 1.0
        n        = len(w)
        leftover = self.discount * n / total if total > 0 else 0.0

        p: dict[str, float] = {}
        for tok, wt in w.items():
            p[tok] = max(wt - self.discount, 0.0) / total

        tc = sum(self.cont.values()) or 1
        for tok, c in self.cont.items():
            if tok not in p and tok not in (START, END):
                p[tok] = leftover * (c / tc)

        z = sum(p.values()) or 1.0
        return {t: v / z for t, v in p.items() if v > 0}

    def ip_probs(self, prefix: list[str], site: str | None, strength: float = 1.0) -> dict[str, float]:
        base = self.next_probs(prefix, site)
        if not base or strength == 0.0:
            return base
        tf = sum(self.freq.values()) or 1
        r  = {}
        for tok, p in base.items():
            rarity  = tf / self.freq.get(tok, 1)
            r[tok]  = (p ** (1.0 - strength)) * (rarity ** strength)
        z = sum(r.values()) or 1.0
        return {t: v / z for t, v in r.items()}

    def children(self, prefix: list[str], site: str | None) -> dict[str, float]:
        out: dict[str, float] = {}
        for w in range(min(self.order, len(prefix)), 0, -1):
            ctx = tuple(prefix[-w:])
            if ctx in self.trans:
                raw   = self.trans[ctx]
                total = sum(raw.values()) or 1
                for tok, cnt in raw.items():
                    if tok not in (START, END) and tok not in out:
                        out[tok] = cnt / total
        return out

    def save(self, path: str) -> None:
        data = {
            "order":      self.order,
            "discount":   self.discount,
            "total":      self.total,
            "vocab":      list(self.vocab),
            "freq":       dict(self.freq),
            "cont":       dict(self.cont),
            "real_vals":  dict(self.real_vals),
            "learned_kw": list(self.learned_kw),
            "trans":      {json.dumps(list(k)): dict(v) for k, v in self.trans.items()},
            "ctx_site":   {json.dumps(list(k)): list(v) for k, v in self.ctx_site.items()},
        }
        with open(path, "w") as f:
            json.dump(data, f)
        print(f"[✓] Saved -> {path}")

    @classmethod
    def load(cls, path: str) -> "Model":
        with open(path) as f:
            data = json.load(f)
        m           = cls(order=data["order"], discount=data.get("discount", 0.75))
        m.total     = data["total"]
        m.vocab     = set(data.get("vocab", []))
        m.freq      = defaultdict(int, data.get("freq", {}))
        m.cont      = defaultdict(int, data.get("cont", {}))
        m.real_vals = defaultdict(list, data.get("real_vals", {}))
        m.learned_kw = set(data.get("learned_kw", []))
        # restore learned keywords into the live KEYWORDS set
        from .tokens import KEYWORDS
        KEYWORDS.update(m.learned_kw)
        for k, v in data["trans"].items():
            m.trans[tuple(json.loads(k))] = defaultdict(int, v)
        for k, v in data.get("ctx_site", {}).items():
            m.ctx_site[tuple(json.loads(k))] = set(v)
        print(f"[✓] Loaded <- {path}  (urls={m.total}  learned_kw={len(m.learned_kw)})")
        return m