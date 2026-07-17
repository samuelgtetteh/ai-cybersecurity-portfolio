# Publishing the RegMap model

The release is built by `scripts/make_regmap_release.py` into `dist/regmap-embedder/`
(self-contained: model + `README.md` model card + `LICENSE` + `hipaa_corpus.csv` +
`regmap_map.py` + `example.py`) and `dist/regmap-embedder-release.zip`.

Build it:
```bash
venv/Scripts/python.exe scripts/make_regmap_release.py
```

## Option A — Hugging Face Hub (recommended; requires YOUR HF account/token)
```bash
pip install -U huggingface_hub
huggingface-cli login                       # paste your HF write token
huggingface-cli upload stetteh/regmap-embedder dist/regmap-embedder . --repo-type model
```
Then anyone can use it:
```python
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("stetteh/regmap-embedder")
```
(The model card `README.md` renders automatically on the model page.)

> The push needs your credentials, so this step is done by you — nothing is uploaded on your behalf.

## Option B — Zip / GitHub Release (no account needed)
Distribute `dist/regmap-embedder-release.zip`. A user unzips and runs:
```bash
pip install -r requirements.txt
python example.py
# or
python regmap_map.py "Enforce multi-factor authentication for remote access."
```

## Option C — Docker image (GHCR; shows under the repo's Packages tab)
A model-serving image (`serve.py` → `POST /map`) built from the release folder:
```bash
docker build -f packaging/regmap/Dockerfile -t ghcr.io/samuelgtetteh/regmap-embedder:0.1 dist/regmap-embedder
# login to GHCR with a token that has write:packages:
gh auth token | docker login ghcr.io -u samuelgtetteh --password-stdin      # or a PAT
docker push ghcr.io/samuelgtetteh/regmap-embedder:0.1
```
Run it:
```bash
docker run -p 8080:8080 ghcr.io/samuelgtetteh/regmap-embedder:0.1
curl -s localhost:8080/map -H 'Content-Type: application/json' -d '{"control":"Enforce MFA for remote access."}'
```
If `gh auth token` lacks the scope, run `gh auth refresh -s write:packages` (or create a classic PAT
with `write:packages`) and `docker login ghcr.io` again.

## Notes
- License: Apache-2.0 (matches the base model `all-MiniLM-L6-v2`).
- `dist/` is git-ignored (the model already lives in `models/regmap-embedder`); the release is
  reproducible from this repo, so it isn't committed.
