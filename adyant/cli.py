import argparse
import sys
import re
from urllib.parse import urlparse

from .model   import Model
from .tokens  import split
from .synonyms import canon
from .domains  import detect, PROFILES
from . import modes as _m

MODES = ["sample", "beam", "rare", "child", "diverse", "deep", "punch"]

_TAG = re.compile(r":[a-z0-9]+(?::[a-z0-9]+)?:")


def _to_ffuf(path, pools):
    markers = {}
    counter = [0]
    def sub(m):
        tag = m.group(0)
        if tag not in markers:
            counter[0] += 1
            markers[tag] = (f"FUZZ{counter[0]}", pools.get(tag, [tag]))
        return markers[tag][0]
    result = _TAG.sub(sub, path)
    wordlists = {name: vals for tag, (name, vals) in markers.items()}
    return result, wordlists

def _to_burp(path):
    n = [0]
    def sub(m):
        n[0] += 1
        return f"\u00a7FUZZ{n[0]}\u00a7"
    return _TAG.sub(sub, path)

def _to_nuclei(path):
    n = [0]
    def sub(m):
        n[0] += 1
        return "{{" + f"FUZZ{n[0]}" + "}}"
    return _TAG.sub(sub, path)


def _build_parser():
    p = argparse.ArgumentParser(
        prog="adyant",
        description=(
            "adyant — smart URL wordlist generator\n"
            "\n"
            "Instead of guessing random paths, adyant learns from a list of real URLs\n"
            "and generates likely paths for a target site. The more URLs you feed it,\n"
            "the smarter it gets.\n"
            "\n"
            "QUICK START\n"
            "-----------\n"
            "  # 1. collect some URLs (burp history, waybackurls, etc.)\n"
            "  cat burp_urls.txt | adyant --train - --seed target.com/api/\n"
            "\n"
            "  # 2. save the trained model so you dont retrain every time\n"
            "  adyant --train urls.txt --save model.json\n"
            "  adyant --model model.json --seed target.com/api/ --mode child\n"
            "\n"
            "  # 3. pipe directly into ffuf\n"
            "  adyant --model model.json --seed target.com/api/ -q --paths-only |\n"
            "    ffuf -u https://target.com/FUZZ -w -\n"
            "\n"
            "MODES\n"
            "-----\n"
            "  sample  — quick pass, generates the most obvious paths first\n"
            "  beam    — deterministic, same results every run, highest confidence\n"
            "  rare    — digs for endpoints that almost never appear (hidden gems where are you?)\n"
            "  child   — given a path like /api/, lists everything under it\n"
            "  diverse — one result per area (/api/, /admin/, /auth/ etc.) before going deep\n"
            "  deep    — generates long, deeply nested paths like /api/v1/orders/42/items/7/refund\n"
            "  punch   — runs ALL modes and merges results; up to count*6 URLs total\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    src = p.add_argument_group("input — where to get training URLs")
    g   = src.add_mutually_exclusive_group()
    g.add_argument("--train", metavar="FILE",
                   help="Text file with one URL per line. Use - to read from stdin.")
    g.add_argument("--model", metavar="FILE",
                   help="Load a model you saved from a previous run.")
    src.add_argument("--min-freq",    metavar="N", type=int, default=30,
                     dest="min_freq",
                     help="How many times a token must appear to be treated as a keyword (default 30).")
    src.add_argument("--min-domains", metavar="N", type=int, default=10,
                     dest="min_domains",
                     help="How many distinct sites a token must appear on to be a known keyword (such as api,admin etc. | default 10).")

    mdl = p.add_argument_group("model settings")
    mdl.add_argument("--context",   metavar="N", type=int,   default=3,    dest="order",
                     help="How many path segments to use as context (default 3). Higher = smarter.")
    mdl.add_argument("--smoothing", metavar="D", type=float, default=0.75, dest="discount",
                     help="Controls how much probability is given to paths not seen in training (default 0.75).")
    mdl.add_argument("--save",      metavar="FILE",
                     help="Save the trained model to a file so you can reuse it later.")

    sd = p.add_argument_group("seed — what to generate paths for")
    sd.add_argument("--seed", metavar="URL",
                    help="e.g. target.com/api/ or target.com/admin/. "
                         "Can also be piped: echo target.com/api/ | adyant --model m.json")
    sd.add_argument("--site-type", metavar="TYPE", dest="site_type",
                    choices=list(PROFILES.keys()) + ["auto"], default="auto",
                    help="Force the site type instead of auto-detecting. "
                         f"Options: {', '.join(PROFILES.keys())}.")

    gen = p.add_argument_group("mode — how to generate")
    gen.add_argument("--mode", metavar="MODE", default="sample", choices=MODES,
                     help="Generation strategy. See MODES above. (default: sample)")
    gen.add_argument("--count", metavar="N", type=int, default=50,
                     help="How many URLs to generate (default 50).")
    gen.add_argument("--depth", metavar="N", type=int, default=7,
                     help="Maximum number of path segments in a generated URL (default 7).")

    tune = p.add_argument_group("tuning")
    tune.add_argument("--temp",       metavar="T", type=float, default=1.0,
                      help="Randomness for sample mode. >1 = more random, <1 = more conservative (default 1.0).")
    tune.add_argument("--beams",      metavar="N", type=int,   default=10,
                      help="How many candidates to track in beam mode (default 10).")
    tune.add_argument("--rarity",     metavar="R", type=float, default=1.0,
                      help="How aggressively to chase rare paths in rare/child mode. 0=off 1=full (default 1.0).")
    tune.add_argument("--walks",      metavar="N", type=int,   default=1,
                      help="How many walks to do in child mode (default 1). More = broader coverage.")
    tune.add_argument("--per-area",   metavar="N", type=int,   default=3, dest="per_area",
                      help="Max paths per subtree in diverse mode before moving on (default 3).")
    tune.add_argument("--depth-push", metavar="B", type=float, default=0.3, dest="depth_bonus",
                      help="How hard to push for longer paths in deep mode (default 0.3).")

    out = p.add_argument_group("output")
    out.add_argument("--out",    metavar="FILE", dest="output",
                     help="Write results to a file instead of printing to screen.")
    out.add_argument("--scores", action="store_true",
                     help="Show a confidence score next to each URL (higher is more likely to exist).")
    out.add_argument("--expand", action="store_true",
                     help="Replace placeholders like :num: with real values seen in training data.")
    out.add_argument("--format", metavar="FMT", default="raw",
                     choices=["raw", "expand", "ffuf", "burp", "nuclei"],
                     help="Output format. raw = plain URLs (default), expand = fill in placeholders, "
                          "ffuf/burp/nuclei = ready to paste into that tool.")
    out.add_argument("--paths-only", action="store_true", dest="paths_only",
                     help="Output just the path (/api/users) not the full URL (https://target.com/api/users). "
                          "Useful when piping into ffuf with -u https://target.com/FUZZ.")
    out.add_argument("-q", "--quiet", action="store_true",
                     help="Suppress progress messages. Use this when piping output to another tool.")

    return p


def _seed_str(args):
    if args.seed:
        return args.seed.strip()
    if not sys.stdin.isatty():
        line = sys.stdin.readline().strip()
        if line:
            return line
    return None


def main():
    parser = _build_parser()
    args   = parser.parse_args()

    def log(msg):
        if not args.quiet:
            print(msg, file=sys.stderr)

    if args.model:
        model = Model.load(args.model)

    elif args.train:
        model = Model(order=args.order, discount=args.discount)
        src   = args.train
        urls  = sys.stdin.readlines() if src == "-" else open(src).readlines()
        model.train(urls, min_freq=args.min_freq, min_domains=args.min_domains)
        if args.save:
            model.save(args.save)

    else:
        parser.error(
            "You need to provide training data or a saved model.\n"
            "  adyant --train urls.txt --seed target.com/api/\n"
            "  adyant --model saved.json --seed target.com/api/"
        )

    seed_str = _seed_str(args)
    if not seed_str:
        if args.save:
            return
        parser.error(
            "No seed URL provided.\n"
            "  adyant --model m.json --seed target.com/api/\n"
            "  echo target.com/api/ | adyant --model m.json"
        )

    raw       = seed_str if "://" in seed_str else "https://" + seed_str
    parsed    = urlparse(raw)
    host      = parsed.netloc
    seed_toks = [canon(t) for t in split(parsed.path, abstract=True)]

    site = args.site_type if args.site_type != "auto" else detect(seed_toks)
    count_hint = f"up to {args.count * 6}" if args.mode == "punch" else str(args.count)
    log(f"[→] seed={seed_str}  type={site or '?'}  mode={args.mode}  count={count_hint}")

    m = args.mode
    if   m == "sample":  results = _m.sample(model, seed_toks, args.count, args.depth, args.temp)
    elif m == "beam":    results = _m.beam(model, seed_toks, args.count, args.depth, args.beams)
    elif m == "rare":    results = _m.rare(model, seed_toks, args.count, args.depth, args.rarity)
    elif m == "child":   results = _m.child(model, seed_toks, args.count, args.depth, args.walks, args.rarity)
    elif m == "diverse": results = _m.diverse(model, seed_toks, args.count, args.depth, args.per_area)
    elif m == "deep":    results = _m.deep(model, seed_toks, args.count, args.depth, args.depth_bonus)
    elif m == "punch":   results = _m.punch(model, seed_toks, args.count, args.depth, args.temp,
                                            args.beams, args.rarity, args.walks,
                                            args.per_area, args.depth_bonus)

    if not results:
        log("[!] nothing generated — try a different mode, a broader seed, or more training data")
        return

    from .expand import Expander
    ex  = Expander(model.real_vals)
    fmt = args.format if args.format != "raw" else ("expand" if args.expand else "raw")

    lines    = []
    ffuf_wls = {}

    for rank, (path, sc) in enumerate(results, 1):
        url = path if args.paths_only else (f"https://{host}{path}" if host else path)

        if fmt == "expand":
            url = ex.expand(url)
        elif fmt == "ffuf":
            url, wls = _to_ffuf(url, model.real_vals)
            ffuf_wls.update(wls)
        elif fmt == "burp":
            url = _to_burp(url)
        elif fmt == "nuclei":
            url = _to_nuclei(url)

        line = f"{rank:>4}.  {sc:>9.3f}  {url}" if args.scores else url
        lines.append(line)

    if fmt == "ffuf" and ffuf_wls:
        log("[ffuf] writing companion wordlists:")
        for name, vals in ffuf_wls.items():
            fname = f"{name}.txt"
            with open(fname, "w") as f:
                f.write("\n".join(vals) + "\n")
            log(f"  {fname}  ({len(vals)} values)")
        wl_args = "  ".join(f"-w {n}.txt:{n}" for n in ffuf_wls)
        log(f"[ffuf] command: ffuf {wl_args} -u \'https://{host}/FUZZ\' -mode clusterbomb")

    text = "\n".join(lines)
    if args.output:
        open(args.output, "w").write(text + "\n")
        log(f"[✓] {len(lines)} URLs written to {args.output}")
    else:
        print(text)
        log(f"[✓] {len(lines)} URLs  (mode={args.mode})")


if __name__ == "__main__":
    main()