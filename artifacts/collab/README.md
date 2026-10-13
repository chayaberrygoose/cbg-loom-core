# artifacts/collab

Storage for prototype collaboration artifacts (images, draft payloads, logs).

Guidelines
- Default behavior in `scripts/fabricate_collab_sample.py` is dry-run only.
- Do not enable publishing without explicit consent and required environment variables.
- Keep any third-party or partner assets out of the public repo when required by NDAs — store externally and reference paths here.

Usage
- Place candidate images in a local path and run the scaffold script with `--images`.
- The script copies images into this folder and writes a draft payload JSON for review.

Safety
- Publishing to external services is gated behind `--publish` + `--confirm-publish` and env var checks.
- This folder is intended for drafts only; do not commit private partner assets to the public repository.
