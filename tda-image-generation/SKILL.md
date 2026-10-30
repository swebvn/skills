---
name: tda-image-generation
description: Generate or edit raster images through the configured TDA OpenAI-compatible proxy, bypassing Codex's built-in Free-plan image-tool gate. Use when the user invokes $tda-image-generation, says tda_image_generation or TDA image generation, explicitly requests the TDA/custom proxy, or asks to generate/edit an image after the built-in image_gen tool is unavailable. Supports text-to-image, up to five reference images, size/quality/background controls, and local PNG/JPEG/WebP output.
---

# TDA Image Generation

Use `scripts/tda_image_generation.py` for generation and editing. The script calls the active TDA provider's OpenAI-compatible Images API and saves decoded image files locally.

## Model

The default is `gpt-image-2.5-sunburst` (highest image quality and edit precision). Pass `--model` to switch:

- `gpt-image-2.5-sunburst` — most capable; slower, best edit precision.
- `gpt-image-2.5-flare` — faster and cheaper in latency; quality comparable to `gpt-image-2`.
- `gpt-image-2` — previous generation; still available.

## Credentials

Resolve credentials at runtime; never copy a token into this skill, prompts, logs, or command arguments.

The script reads `[model_providers.tdaproxy]` from `~/.codex/config.toml` by default. Resolution precedence is:

1. `TDA_IMAGE_BASE_URL` and `TDA_IMAGE_TOKEN`
2. The provider's `base_url` and environment variable named by `env_key`
3. The provider's `experimental_bearer_token`

Use `--provider` only when the user requests another configured provider.

## Generate

Run:

```bash
python3 <skill-dir>/scripts/tda_image_generation.py generate \
  --prompt "<production-ready image prompt>" \
  --output "<absolute-output-path>.png"
```

Add `--quality low|medium|high|xhigh|max|auto`, `--size WIDTHxHEIGHT|auto`, `--background auto|opaque|transparent`, `--format png|jpeg|webp`, or `--n 1..5` only when needed. Use `--overwrite` only when the user explicitly asked to replace an existing file.

## Edit

Inspect local inputs with `view_image` first, then run:

```bash
python3 <skill-dir>/scripts/tda_image_generation.py edit \
  --prompt "<state the change and invariants>" \
  --input "<absolute-input-path>" \
  --output "<absolute-output-path>.png"
```

Repeat `--input` for up to five reference images. Save non-destructively by default. State exactly what changes and what must remain unchanged.

## Parameter limits

The `tdaproxy` endpoint does not fully honor request parameters. Verified behavior:

- `--size` is ignored; the endpoint returns its own resolution (observed `1536x1024` and `1254x1254`).
- `--quality` is downgraded or remapped (`high` → `medium`, `max`, `low`, and invalid values → `low`).
- `--background` and `--format` are echoed correctly.

The script compares requested values against the response and reports each mismatch as a `warnings` entry plus a stderr line. Treat `size` and `quality` as best-effort hints on this provider, and read the actual saved image rather than assuming the requested geometry. Other providers selected with `--provider` may honor them normally.

## Workflow

1. Shape a concise production prompt: scene, subject, style, composition, lighting, and constraints.
2. Generate or edit directly unless required input images are missing.
3. Allow up to three minutes for the proxy response.
4. Inspect every saved image with `view_image`.
5. If the output misses a requirement, make one targeted prompt change and rerun to a new filename.
6. Render the selected image inline and report its absolute saved path.

For preview-only work, save under `$CODEX_HOME/generated_images/tda/`. For project assets, save inside the project and update consumers as requested.

## Failure handling

- Do not print or expose bearer tokens.
- Retry `429` and `5xx` failures once after a short delay; do not retry authentication, moderation, or invalid-request errors unchanged.
- If the proxy rejects the Images API contract, report the HTTP status and sanitized error, then inspect the proxy contract before changing endpoints.
- Do not silently fall back to OpenAI's built-in image tool or another provider.
