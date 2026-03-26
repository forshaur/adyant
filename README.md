
# Adyant  ([/ɑːdiˌjɑːnt/](https://www.wisdomlib.org/definition/adyant))

**Smart Markov-chain URL wordlist generator.**

`adyant` learns real URL patterns from any corpus (Burp history, Wayback, etc.) and generates highly relevant paths for a target site — far smarter than random brute-force wordlists.

Perfect for recon, directory busting, API enumeration, and bug bounty hunting.

However, the quality of the output you get is highly influenced by the training corpus - so take care of that.

This project is backed by my research, I'll publish the research paper soon.
<img width="513" height="510" alt="image1" src="https://github.com/user-attachments/assets/f0d97cb6-702d-47fb-8875-09a805e2b8cf" />


## Quick Start

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
