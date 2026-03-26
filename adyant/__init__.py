"""
adyant — Markov chain URL wordlist generator.

Quick start (library usage):
  from adyant import Model, guess

  model = Model().train(open("urls.txt").readlines())
  model.save("model.json")

  # Generate with any mode
  results = guess(model, seed="example.com/api/v1/", mode="sibling", count=40)
  for url, score in results:
      print(url)

Modes:
  sample  — fast, follows common paths           (default)
  beam    — deterministic, highest confidence
  rare    — surfaces the rarest endpoints
  sibling — IP walk + exhaustive child listing    (novel)
  diverse — one result per subtree, broad recon
  deep    — generates longer / deeper paths
"""

from .model   import Model
from .tokens  import split, label, KEYWORDS, TYPES
from .synonyms import canon, GROUPS
from .domains  import detect, PROFILES
from .expand  import expand
from . import modes as _modes

__version__ = "1.0.0"
__all__ = ["Model", "guess", "expand", "split", "label", "canon", "detect"]


def guess(
    model:       "Model",
    seed:        str,
    mode:        str  = "sample",
    count:       int  = 50,
    max_depth:   int  = 7,
    expand_vals: bool = False,
    # mode-specific options
    temp:        float = 1.0,    # sample / deep
    beam_width:  int   = 10,     # beam
    strength:    float = 1.0,    # rare / sibling
    walks:       int   = 5,      # sibling
    per_subtree: int   = 3,      # diverse
    depth_bonus: float = 0.3,    # deep
) -> list[tuple[str, float]]:
    """
    Generate URL guesses from a seed prefix using the chosen mode.

    Args:
        model       — trained Model instance
        seed        — seed URL or path, e.g. "example.com/api/v1/"
        mode        — one of: sample, beam, rare, sibling, diverse, deep
        count       — how many URLs to return
        max_depth   — maximum path length in tokens
        expand_vals — if True, replace :num: / :uuid: etc. with real values
        temp        — sampling temperature for sample mode (>1 = more random)
        beam_width  — parallel beams for beam mode
        strength    — IP inversion strength for rare/sibling (1.0 = full)
        walks       — independent walks for sibling mode
        per_subtree — max results per subtree for diverse mode
        depth_bonus — depth encouragement for deep mode

    Returns:
        List of (url_string, score) sorted best-first.
        score is log-probability — higher (less negative) is more confident.
    """
    from .tokens  import split
    from .synonyms import canon
    from urllib.parse import urlparse

    # Parse seed into host + token list
    raw   = seed if "://" in seed else "https://" + seed
    p     = urlparse(raw)
    host  = p.netloc
    toks  = [canon(t) for t in split(p.path, abstract=True)]

    # Dispatch to the right mode
    mode = mode.lower()
    if mode == "sample":
        results = _modes.sample(model, toks, count, max_depth, temp)
    elif mode == "beam":
        results = _modes.beam(model, toks, count, max_depth, beam_width)
    elif mode == "rare":
        results = _modes.rare(model, toks, count, max_depth, strength)
    elif mode == "sibling":
        results = _modes.sibling(model, toks, count, max_depth, walks, strength)
    elif mode == "diverse":
        results = _modes.diverse(model, toks, count, max_depth, per_subtree)
    elif mode == "deep":
        results = _modes.deep(model, toks, count, max_depth, depth_bonus)
    else:
        raise ValueError(f"Unknown mode '{mode}'. "
                         "Choose: sample, beam, rare, sibling, diverse, deep")

    # Prepend host and optionally expand placeholders
    from .expand import expand as _expand
    output = []
    for path, score in results:
        url = f"https://{host}{path}" if host else path
        if expand_vals:
            url = _expand(url)
        output.append((url, score))

    return output
