"""
tests/test_all.py — Basic tests for adyant.

Run with:  pytest tests/
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from adyant.tokens   import split, label
from adyant.synonyms import canon
from adyant.domains  import detect
from adyant.expand   import expand
from adyant.model    import Model
from adyant          import guess
SAMPLE_URLS = [
    "https://example.com/api/v1/users/profile",
    "https://example.com/api/v1/users/settings",
    "https://example.com/api/v1/users/avatar",
    "https://example.com/api/v1/admin/dashboard",
    "https://example.com/api/v1/admin/debug",
    "https://example.com/api/v1/auth/login",
    "https://example.com/api/v1/auth/logout",
    "https://example.com/api/v2/users/profile",
    "https://example.com/api/v2/admin/reports",
]


# ── tokens ────────────────────────────────────────────────────────────────

def test_label_keyword():
    assert label("users") == "users"

def test_label_num():
    assert label("42") == ":num:"

def test_label_uuid():
    assert label("550e8400-e29b-41d4-a716-446655440000") == ":uuid:"

def test_label_date():
    assert label("2024-01-15") == ":date:"

def test_label_word():
    assert label("my-blog-post") == ":word:"

def test_split_basic():
    # split() returns typed tokens but does NOT canonicalise (that's synonyms.canon)
    toks = split("/api/v1/users/42/profile")
    assert toks == ["api", "v1", "users", ":num:", "profile"]

def test_split_no_abstract():
    toks = split("/api/v1/users", abstract=False)
    assert toks == ["api", "v1", "users"]


# ── synonyms ──────────────────────────────────────────────────────────────

def test_canon_delete():
    assert canon("remove") == canon("delete") == canon("destroy")

def test_canon_users():
    assert canon("users") == canon("account") == canon("member")

def test_canon_passthrough():
    assert canon("graphql") == "graphql"


# ── domains ───────────────────────────────────────────────────────────────

def test_detect_api():
    assert detect(["api", "v1", "users"]) == "api"

def test_detect_cms():
    assert detect(["blog", "post", "category"]) == "cms"

def test_detect_admin():
    assert detect(["admin", "dashboard", "logs"]) == "admin"


# ── expand ────────────────────────────────────────────────────────────────

def test_expand_num():
    result = expand("/api/users/:num:/profile")
    assert ":num:" not in result

def test_expand_uuid():
    result = expand("/api/:uuid:/data")
    assert ":uuid:" not in result


# ── model ─────────────────────────────────────────────────────────────────

def _trained():
    m = Model(order=2)
    m.train(SAMPLE_URLS)
    return m

def test_model_trains():
    m = _trained()
    assert m.total == len(SAMPLE_URLS)
    assert len(m.vocab) > 0
    assert len(m.transitions) > 0

def test_model_next_probs():
    m = _trained()
    from adyant.model import START
    probs = m.next_probs([START, START, "api"], site_type="api")
    assert isinstance(probs, dict)
    assert len(probs) > 0
    assert abs(sum(probs.values()) - 1.0) < 1e-6  # sums to 1

def test_model_save_load(tmp_path):
    m = _trained()
    path = str(tmp_path / "model.json")
    m.save(path)
    m2 = Model.load(path)
    assert m2.total == m.total
    assert m2.vocab == m.vocab


# ── modes ─────────────────────────────────────────────────────────────────

def _run(mode, **kw):
    m = _trained()
    return guess(m, seed="example.com/api/v1/", mode=mode, count=10, **kw)

def test_mode_sample():
    r = _run("sample")
    assert len(r) > 0
    assert all(isinstance(url, str) for url, _ in r)

def test_mode_beam():
    r = _run("beam", beam_width=5)
    assert len(r) > 0

def test_mode_rare():
    r = _run("rare", strength=1.0)
    assert len(r) > 0

def test_mode_sibling():
    r = _run("sibling", walks=3)
    assert len(r) > 0

def test_mode_diverse():
    r = _run("diverse", per_subtree=2)
    assert len(r) > 0

def test_mode_deep():
    r = _run("deep", depth_bonus=0.5)
    assert len(r) > 0

def test_bad_mode():
    import pytest
    with pytest.raises(ValueError):
        _run("nonexistent")

def test_scores_are_finite():
    r = _run("sample")
    import math
    assert all(math.isfinite(score) for _, score in r)
