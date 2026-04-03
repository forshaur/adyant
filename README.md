<p align="center">
  <img src="https://github.com/user-attachments/assets/509909a7-ca19-4ae9-837b-fddaeb9a142f" alt="Adyant Logo" width="400">
</p>

<h1 align="center">Adyant</h1>

<p align="center">
  <strong>Smart Markov-chain URL wordlist generator for fuzzing and recon.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/adyant/"><img src="https://img.shields.io/pypi/v/adyant" alt="PyPI"></a>
  <a href="https://github.com/forshaur/adyant/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://github.com/forshaur/adyant"><img src="https://img.shields.io/badge/Python-3.10%2B-brightgreen" alt="Python 3.10+"></a>
</p>

<br>

Instead of brute-forcing targets with massive, static, and noisy wordlists, **Adyant** learns from real URL patterns (via Burp history, Wayback, etc.) and generates statistically likely paths tailored specifically to your target. 

If you want to find hidden endpoints with fewer requests and less noise, you're in the right place.

<p align="center">
  <img src="https://github.com/user-attachments/assets/75cbe049-1b67-4813-ab48-f9f034f8eef9" alt="Adyant Demo" width="700">
</p>

we're taking log of probabilities, so the result is a negative value, don't worry about it.


---

## ⚡ Quickstart (Time-to-First-Value)

Get Adyant running locally in under 30 seconds.

**1. Install via pip**
```bash
pip install adyant
```
**Recommended**
```bash
git clone https://github.com/forshaur/adyant.git
cd adyant
pip install .
```
**2. Train & Fuzz (Seamless Pipeline)**

Feed it URLs, give it a seed, and pipe it directly into your favorite fuzzer:

Bash

```
cat burp_urls.txt | adyant --train - --seed https://target.com/api/ -q --paths-only | ffuf -u https://target.com/FUZZ -w -

```

## ✨ The Value Proposition

Why replace your static wordlists with Adyant?

-   🧠 **Context-Aware Fuzzing:** It doesn't just guess `/admin`; it calculates the probability of `/admin/v2/metrics` based on real-world transition states.
    
-   🎯 **Multiple Attack Modes:** Need the most obvious paths? Use `sample`. Looking for deeply nested routes? Use `deep`. Hunting for hidden gems? Use `rare`.
    
-   🛠️ **Native Integrations:** Outputs natively formatted payloads for `ffuf`, `burp`, and `nuclei` with zero parsing scripts required.
    
-   🤖 **Smart Synonym Discovery:** Optional ML-driven clustering (via `scikit-learn` & `sentence_transformers`) identifies semantic domain clusters and token synonyms automatically.
    
-   📉 **Reduced Request Volume:** Higher hit rates with a fraction of the HTTP requests. Stay under WAF rate limits.
    

## 📖 Documentation & Usage

Adyant is highly tunable. You can adjust the Markov context (`--context`), control rarity (`--rarity`), and format outputs to include explicit confidence scores (`--scores`).

For advanced configurations, saving/loading models, and a detailed breakdown of all generation modes, please refer to the official documentation:

👉 **Read the full Adyant [Wiki](https://github.com/forshaur/adyant/wiki/)**

## 🤝 Community & Support

-   **Issues & Bugs:** Encountered an error? Please [open an issue](https://github.com/forshaur/adyant/issues).
    
-   **Research:** This project is backed by ongoing security research, which will be published and linked here shortly.
    

> ⭐️ **Don't forget to star it so that you may use it later.**
