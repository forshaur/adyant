import math
import random
from .model import Model, START, END
from .domains import detect


def _path(toks): return "/" + "/".join(toks)
def _prep(seed, order): return [START] * order + list(seed)
def _area(path):
    parts = [p for p in path.split("/") if p]
    return parts[1] if len(parts) > 1 else (parts[0] if parts else "")


def sample(model, seed, count=50, depth=7, temp=1.0):
    """Follow highest-probability transitions. Good for a first pass."""
    site  = detect(seed)
    found = {}
    for _ in range(count * 25):
        if len(found) >= count:
            break
        path, sc = _walk(model, seed, site, depth, temp, ip=0.0)
        if path and path not in found:
            found[path] = sc
    return sorted(found.items(), key=lambda x: -x[1])


def beam(model, seed, count=50, depth=7, width=10):
    """Deterministic beam search — reproducible, highest-confidence paths."""
    site  = detect(seed)
    live  = [(_prep(seed, model.order), list(seed), 0.0)]
    done  = []

    for _ in range(depth - len(seed)):
        nxt = []
        for pre, toks, sc in live:
            p = model.next_probs(pre, site)
            if not p:
                done.append((_path(toks), sc))
                continue
            for tok, prob in p.items():
                ns = sc + math.log(prob + 1e-12)
                if tok == END:
                    done.append((_path(toks), ns))
                else:
                    nxt.append((pre + [tok], toks + [tok], ns))
        if not nxt:
            break
        nxt.sort(key=lambda x: -x[2])
        live = nxt[:width]

    for pre, toks, sc in live:
        done.append((_path(toks), sc))

    best = {}
    for path, sc in done:
        if path not in best or sc > best[path]:
            best[path] = sc
    return sorted(best.items(), key=lambda x: -x[1])[:count]


def rare(model, seed, count=50, depth=7, strength=1.0):
    """Global IP inversion — actively seeks the rarest endpoints."""
    site  = detect(seed)
    found = {}
    for _ in range(count * 25):
        if len(found) >= count:
            break
        path, sc = _walk(model, seed, site, depth, temp=1.0, ip=strength)
        if path and path not in found:
            found[path] = sc
    return sorted(found.items(), key=lambda x: -x[1])


def child(model, seed, count=50, depth=7, walks=5, strength=1.0):
    """
    Two-phase: IP walk to a rare node, then list ALL its children exhaustively.

    The IP walk steers toward low-density subtrees (e.g. /admin/ over /users/).
    At every step, all children of the current parent are enumerated regardless
    of frequency — so /admin/debug (seen twice) can't be drowned out by
    /admin/dashboard (seen 500 times).
    """
    site  = detect(seed)
    found = {}

    for _ in range(walks):
        pre   = _prep(seed, model.order)
        toks  = list(seed)
        sc    = 0.0

        for _ in range(depth - len(seed)):
            p = model.ip_probs(pre, site, strength)
            if not p:
                break
            tok = random.choices(list(p), weights=list(p.values()))[0]
            if tok == END:
                break
            sc += math.log(p[tok] + 1e-12)
            toks.append(tok)
            pre.append(tok)

            # enumerate every child of the parent context
            for kid, kp in model.children(pre[:-1], site).items():
                if kid in (START, END):
                    continue
                kpath = _path(toks[:-1] + [kid])
                kscore = sc + math.log(kp + 1e-12)
                if kpath not in found or kscore > found[kpath]:
                    found[kpath] = kscore

        if toks:
            nav = _path(toks)
            if nav not in found or sc > found[nav]:
                found[nav] = sc

    return sorted(found.items(), key=lambda x: -x[1])[:count]


def diverse(model, seed, count=50, depth=7, per_area=3):
    """Breadth-first — enforces a quota per subtree before going deeper."""
    site   = detect(seed)
    found  = {}
    bucket = {}

    for strict in (True, False):
        for _ in range(count * 50):
            if len(found) >= count:
                break
            path, sc = _walk(model, seed, site, depth, temp=1.0, ip=0.0)
            if not path or path in found:
                continue
            area = _area(path)
            if strict and bucket.get(area, 0) >= per_area:
                continue
            found[path]   = sc
            bucket[area]  = bucket.get(area, 0) + 1
        if len(found) >= count:
            break

    return sorted(found.items(), key=lambda x: -x[1])


def deep(model, seed, count=50, depth=10, bonus=0.3):
    """Depth-weighted sampling — pushes generation to produce longer paths."""
    site  = detect(seed)
    found = {}
    for _ in range(count * 25):
        if len(found) >= count:
            break
        path, sc = _walk_deep(model, seed, site, depth, bonus)
        if path and path not in found:
            found[path] = sc
    return sorted(found.items(), key=lambda x: -x[1])


# ── shared walk functions ─────────────────────────────────────────────────

def _walk(model, seed, site, depth, temp, ip):
    pre  = _prep(seed, model.order)
    toks = list(seed)
    sc   = 0.0
    for _ in range(depth - len(seed)):
        p = model.ip_probs(pre, site, ip) if ip > 0 else model.next_probs(pre, site)
        if not p:
            break
        if temp != 1.0:
            p = {t: v ** (1.0 / temp) for t, v in p.items()}
            z = sum(p.values()) or 1.0
            p = {t: v / z for t, v in p.items()}
        tok = random.choices(list(p), weights=list(p.values()))[0]
        if tok == END:
            break
        sc += math.log(p[tok] + 1e-12)
        toks.append(tok)
        pre.append(tok)
    return (_path(toks), sc) if toks else ("", float("-inf"))


def _walk_deep(model, seed, site, depth, bonus):
    pre   = _prep(seed, model.order)
    toks  = list(seed)
    sc    = 0.0
    d     = len(seed)
    for _ in range(depth - len(seed)):
        p = model.next_probs(pre, site)
        if not p:
            break
        adj = {}
        for tok, prob in p.items():
            b       = bonus * d if tok != END else 0.0
            adj[tok] = math.exp(math.log(prob + 1e-12) + b)
        z   = sum(adj.values()) or 1.0
        adj = {t: v / z for t, v in adj.items()}
        tok = random.choices(list(adj), weights=list(adj.values()))[0]
        if tok == END:
            break
        sc += math.log(adj[tok] + 1e-12)
        toks.append(tok)
        pre.append(tok)
        d += 1
    return (_path(toks), sc) if toks else ("", float("-inf"))