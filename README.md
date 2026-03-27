
# Adyant  ([/ɑːdiˌjɑːnt/](https://www.wisdomlib.org/definition/adyant))

**Smart Markov-chain URL wordlist generator.**

`adyant` learns real URL patterns from any corpus (Burp history, Wayback, etc.) and generates highly relevant paths for a target site — far smarter than random brute-force wordlists.

Perfect for recon, directory busting, API enumeration, and bug bounty hunting.

#### Why to use `adyant`?
* saves time by finding obvious and rare endpoints quickly.
* higher hit rates with fewer requests.
* reduces noice
* can be integrated in workflows (stay ahead over other hackers who use old and slow wordlist fuzzing)

<img width="513" height="510" alt="image1" src="https://github.com/user-attachments/assets/dd8eacc7-2307-4928-a3bb-4e3dccda1f0b" />

`however, quality of the output is highly influenced by the training corpus you provide it - keep that in mind.`
additionally, this project is backed by my research which I'll attatch here once I publish it.

## Quick Start

#### Please raise an issue, if you encounter one.

### 1. Install
```bash
pip install adyant
```

### 2. Train once 
```bash
# Train from a file of URLs
adyant --train urls.txt --save model.json

# Or pipe from anywhere (waybackurls, Burp export, etc.)
cat my_urls.txt | adyant --train - --save model.json
```

### 3. Generate wordlists
```bash
# Most likely paths under a prefix (default = sample mode)
adyant --model model.json --seed target.com/api/ --count 100

# One-level children only (best for fuzzing)
adyant --model model.json --seed target.com/api/ --mode child --count 50

# Pipe directly to ffuf (quiet + paths-only)
adyant --model model.json --seed target.com/api/ -q --paths-only --format ffuf | \
  ffuf -u https://target.com/FUZZ -w -
```

**Useful flags:**
- `--expand` → replaces `:num:`, `:uuid:`, etc. with real values from training
- `--scores` → shows confidence next to each URL
- `--format ffuf|burp|nuclei` → ready-to-paste output
- `--paths-only` → just the path (perfect for `-u https://target.com/FUZZ`)

**Available modes** (use `--mode <name>`):
- `sample` (default) – fast & obvious paths
- `child` – direct children only
- `rare` – hidden gems where are you?
- `beam` – deterministic & highest confidence
- `diverse` – broad coverage across subtrees
- `deep` – long nested paths

Run `adyant --help` for the short version or see **[wiki.md](wiki.md)** for everything else.
