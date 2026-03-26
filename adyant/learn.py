from __future__ import annotations
from collections import defaultdict
import re


def _has_sklearn():
    try:
        import sklearn; return True
    except ImportError:
        return False

def _has_transformers():
    try:
        import sentence_transformers; return True
    except ImportError:
        return False


# ── Synonym discovery ─────────────────────────────────────────────────────

def discover_synonyms(paths, sim_threshold=0.5, min_token_freq=1):
    """
    Find groups of tokens likely to be synonyms by comparing their
    positional co-occurrence patterns across training paths.

    Tokens that appear at the same depth, after the same predecessor,
    before the same successor are likely interchangeable (e.g. delete/remove/destroy).

    Requires scikit-learn. Returns empty list if not installed.
    If sentence-transformers is installed, uses semantic embeddings instead
    (better for synonyms that appear in different structural positions).
    """
    if not _has_sklearn():
        return []
    if _has_transformers():
        return _syn_transformer(paths, sim_threshold, min_token_freq)
    return _syn_cooccur(paths, sim_threshold, min_token_freq)


def _syn_cooccur(paths, sim_thresh, min_freq):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import DBSCAN
    import numpy as np

    positional = defaultdict(list)
    for path in paths:
        for i, tok in enumerate(path):
            prev = path[i - 1] if i > 0            else "__start__"
            nxt  = path[i + 1] if i < len(path) - 1 else "__end__"
            positional[tok].append(f"prev_{prev}")
            positional[tok].append(f"next_{nxt}")
            positional[tok].append(f"depth_{i}")

    freq = defaultdict(int)
    for path in paths:
        for tok in path:
            freq[tok] += 1

    vocab  = {t for t in positional if freq[t] >= min_freq}
    if len(vocab) < 4:
        return []

    tokens = sorted(vocab)
    docs   = [" ".join(positional[t]) for t in tokens]

    vec  = TfidfVectorizer()
    mat  = vec.fit_transform(docs)
    sim  = cosine_similarity(mat)
    dist = np.clip(1.0 - sim, 0.0, 1.0)

    eps    = 1.0 - sim_thresh
    labels = DBSCAN(eps=eps, min_samples=2, metric="precomputed").fit_predict(dist)

    raw: dict[int, list] = defaultdict(list)
    for tok, lbl in zip(tokens, labels):
        if lbl != -1:
            raw[lbl].append(tok)

    out = []
    for members in raw.values():
        for sub in _split_antonyms(members):
            if len(sub) >= 2:
                out.append(set(sub))
    return out


# Known antonym pairs — co-occur in same URL position but should NOT be merged.
# CRUD opposites (create/delete) are intentionally absent: both are useful
# at the same position and we want to generate both directions.
_ANTONYMS = {
    frozenset({"login",     "logout"}),
    frozenset({"signin",    "signout"}),
    frozenset({"logon",     "logoff"}),
    frozenset({"start",     "stop"}),
    frozenset({"enable",    "disable"}),
    frozenset({"lock",      "unlock"}),
    frozenset({"subscribe", "unsubscribe"}),
    frozenset({"publish",   "unpublish"}),
    frozenset({"activate",  "deactivate"}),
    frozenset({"approve",   "reject"}),
    frozenset({"ban",       "unban"}),
    frozenset({"open",      "close"}),
}


def _split_antonyms(members):
    if len(members) < 2:
        return [members]

    n   = len(members)
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if frozenset({members[i], members[j]}) not in _ANTONYMS:
                adj[i].add(j)
                adj[j].add(i)

    visited    = set()
    components = []

    def dfs(node, comp):
        visited.add(node)
        comp.append(members[node])
        for nb in adj[node]:
            if nb not in visited:
                dfs(nb, comp)

    for i in range(n):
        if i not in visited:
            comp = []
            dfs(i, comp)
            components.append(comp)

    return components


def _syn_transformer(paths, sim_thresh, min_freq):
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.cluster import DBSCAN
    import numpy as np

    freq = defaultdict(int)
    for path in paths:
        for tok in set(path):
            freq[tok] += 1

    tokens = sorted(t for t, c in freq.items() if c >= min_freq)
    if len(tokens) < 4:
        return []

    vecs   = SentenceTransformer("all-MiniLM-L6-v2").encode(tokens, show_progress_bar=False)
    sim    = cosine_similarity(vecs)
    dist   = np.clip(1.0 - sim, 0.0, 1.0)
    labels = DBSCAN(eps=1.0 - sim_thresh, min_samples=2, metric="precomputed").fit_predict(dist)

    clusters = defaultdict(list)
    for tok, lbl in zip(tokens, labels):
        if lbl != -1:
            clusters[lbl].append(tok)

    return [set(v) for v in clusters.values() if len(v) >= 2]


# ── Domain cluster discovery ──────────────────────────────────────────────

def discover_domains(paths, n_clusters=None, max_clusters=12):
    """
    Discover domain clusters from the corpus itself via K-Means on TF-IDF
    path vectors, then name each cluster from its centroid keywords.

    Returns {cluster_name: set_of_keywords}. Empty dict if sklearn missing.
    """
    if not _has_sklearn():
        return {}

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import numpy as np
    import warnings

    docs = [" ".join(p) for p in paths if p]
    if len(docs) < 4:
        return {}

    vec = TfidfVectorizer(min_df=2)
    try:
        mat = vec.fit_transform(docs)
    except Exception:
        return {}

    if mat.shape[1] == 0:
        return {}

    k = n_clusters or _best_k(mat, min(max_clusters, len(docs) // 3))
    if k < 2:
        return {}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        km     = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(mat)

    features = vec.get_feature_names_out()
    out      = {}
    for cid in range(k):
        centroid = km.cluster_centers_[cid]
        top_idx  = centroid.argsort()[-10:][::-1]
        kws      = {features[i] for i in top_idx if centroid[i] > 0.01}
        if kws:
            out[_name_cluster(kws, cid)] = kws

    return out


def _best_k(mat, max_k):
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import warnings

    best_k, best_sc = 2, -1.0
    for k in range(2, max_k + 1):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lbl = KMeans(n_clusters=k, random_state=42, n_init="auto").fit_predict(mat)
        if len(set(lbl)) < 2:
            continue
        try:
            sc = silhouette_score(mat, lbl, sample_size=min(1000, mat.shape[0]))
            if sc > best_sc:
                best_sc, best_k = sc, k
        except Exception:
            continue
    return best_k


_CLUSTER_SIGNALS = [
    ("api",     ["api", "v1", "v2", "v3", "graphql", "rest", "endpoint"]),
    ("auth",    ["login", "logout", "signin", "auth", "password", "token", "oauth", "sso"]),
    ("admin",   ["admin", "dashboard", "audit", "logs", "report", "metrics", "manage"]),
    ("media",   ["gallery", "photo", "image", "upload", "thumb", "album", "cdn"]),
    ("shop",    ["cart", "checkout", "order", "product", "payment", "billing"]),
    ("cms",     ["blog", "post", "article", "category", "tag", "feed", "archive"]),
    ("account", ["account", "profile", "settings", "preferences", "me", "user"]),
    ("search",  ["search", "find", "query", "filter", "results", "suggest"]),
]


def _name_cluster(keywords, fallback_id):
    for name, signals in _CLUSTER_SIGNALS:
        if any(s in keywords for s in signals):
            return name
    return f"cluster_{fallback_id}"