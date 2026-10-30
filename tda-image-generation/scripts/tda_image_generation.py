#!/usr/bin/env python3
"""Generate or edit images through a configured OpenAI-compatible TDA proxy."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


DEFAULT_PROVIDER = "tdaproxy"
DEFAULT_MODEL = "gpt-image-2.5-sunburst"
QUALITY_CHOICES = ["low", "medium", "high", "xhigh", "max", "auto"]
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_USER_AGENT = "Codex Desktop/0.148.0-alpha.9 (Mac OS; arm64) tda-image-generation/1.0"
MAX_IMAGES = 5
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class TDAImageError(RuntimeError):
    """A sanitized error suitable for terminal output."""


def default_config_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "config.toml"
    return Path.home() / ".codex" / "config.toml"


def load_provider(config_path: Path, provider_name: str) -> dict[str, Any]:
    try:
        with config_path.open("rb") as handle:
            config = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise TDAImageError(f"Codex config not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise TDAImageError(f"Invalid Codex config: {exc}") from exc

    providers = config.get("model_providers")
    if not isinstance(providers, dict):
        raise TDAImageError("Codex config has no [model_providers] table")
    provider = providers.get(provider_name)
    if not isinstance(provider, dict):
        raise TDAImageError(f"Model provider is not configured: {provider_name}")
    return provider


def resolve_connection(
    provider: dict[str, Any], token_env: str
) -> tuple[str, str, dict[str, str], dict[str, str]]:
    base_url = os.environ.get("TDA_IMAGE_BASE_URL") or provider.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise TDAImageError(
            "Missing image API base URL; set TDA_IMAGE_BASE_URL or provider.base_url"
        )

    token = os.environ.get(token_env)
    if not token:
        env_key = provider.get("env_key")
        if isinstance(env_key, str) and env_key:
            token = os.environ.get(env_key)
    if not token:
        configured_token = provider.get("experimental_bearer_token")
        if isinstance(configured_token, str):
            token = configured_token
    if not token:
        raise TDAImageError(
            f"Missing bearer token; set {token_env}, provider.env_key, or "
            "provider.experimental_bearer_token"
        )

    headers: dict[str, str] = {}
    static_headers = provider.get("http_headers")
    if isinstance(static_headers, dict):
        headers.update(
            {str(key): str(value) for key, value in static_headers.items()}
        )
    env_headers = provider.get("env_http_headers")
    if isinstance(env_headers, dict):
        for key, env_name in env_headers.items():
            value = os.environ.get(str(env_name))
            if value:
                headers[str(key)] = value

    query_params: dict[str, str] = {}
    configured_query = provider.get("query_params")
    if isinstance(configured_query, dict):
        query_params.update(
            {str(key): str(value) for key, value in configured_query.items()}
        )

    return base_url.rstrip("/"), token, headers, query_params


def sanitize(text: str, token: str, base_url: str) -> str:
    sanitized = text.replace(token, "<redacted>") if token else text
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.path and parsed.path != "/":
        sanitized = sanitized.replace(parsed.path, "/<redacted-path>")
    return sanitized[:4000]


def endpoint_url(
    base_url: str, path: str, query_params: dict[str, str]
) -> str:
    url = f"{base_url}/{path.lstrip('/')}"
    if query_params:
        url = f"{url}?{urllib.parse.urlencode(query_params)}"
    return url


def request_json(
    *,
    url: str,
    payload: dict[str, Any],
    token: str,
    extra_headers: dict[str, str],
    timeout: int,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": os.environ.get("TDA_IMAGE_USER_AGENT", DEFAULT_USER_AGENT),
        "originator": "Codex Desktop",
        "x-codex-image-turn-id": str(uuid.uuid4()),
        **extra_headers,
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    for attempt in range(2):
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise TDAImageError("Image endpoint returned a non-object JSON response")
                return result
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code in RETRYABLE_STATUS and attempt == 0:
                time.sleep(2)
                continue
            raise TDAImageError(
                f"Image endpoint returned HTTP {exc.code}: {raw}"
            ) from exc
        except urllib.error.URLError as exc:
            if attempt == 0:
                time.sleep(2)
                continue
            raise TDAImageError(f"Image endpoint request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise TDAImageError("Image endpoint returned invalid JSON") from exc

    raise TDAImageError("Image endpoint request failed after retry")


def image_to_data_url(path: Path) -> str:
    if not path.is_file():
        raise TDAImageError(f"Input image not found: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise TDAImageError(
            f"Unsupported input image type for {path}; use PNG, JPEG, or WebP"
        )
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def output_paths(output: Path, count: int, output_format: str) -> list[Path]:
    expected_suffix = ".jpg" if output_format == "jpeg" else f".{output_format}"
    if not output.suffix:
        output = output.with_suffix(expected_suffix)
    paths = [output]
    for index in range(2, count + 1):
        paths.append(output.with_name(f"{output.stem}-{index}{output.suffix}"))
    return paths


def decode_image(item: dict[str, Any], token: str, timeout: int) -> bytes:
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise TDAImageError("Image endpoint returned invalid base64 data") from exc

    image_url = item.get("url")
    if isinstance(image_url, str) and image_url:
        headers: dict[str, str] = {}
        if urllib.parse.urlsplit(image_url).scheme in {"http", "https"}:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(image_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.URLError as exc:
            raise TDAImageError(f"Failed to download generated image: {exc.reason}") from exc

    raise TDAImageError("Image response item has neither b64_json nor url")


def save_images(
    response: dict[str, Any],
    *,
    output: Path,
    output_format: str,
    token: str,
    timeout: int,
    overwrite: bool,
) -> list[Path]:
    data = response.get("data")
    if not isinstance(data, list) or not data:
        error = response.get("error")
        if error is not None:
            raise TDAImageError(f"Image endpoint error: {json.dumps(error)}")
        raise TDAImageError("Image endpoint returned no image data")
    if len(data) > MAX_IMAGES:
        raise TDAImageError(f"Image endpoint returned more than {MAX_IMAGES} images")

    paths = output_paths(output, len(data), output_format)
    for path in paths:
        if path.exists() and not overwrite:
            raise TDAImageError(f"Output already exists: {path}; choose a new path")

    saved: list[Path] = []
    for item, path in zip(data, paths, strict=True):
        if not isinstance(item, dict):
            raise TDAImageError("Image endpoint returned an invalid data item")
        image_bytes = decode_image(item, token, timeout)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if overwrite else "xb"
        with path.open(mode) as handle:
            handle.write(image_bytes)
        saved.append(path.resolve())
    return saved


def add_common_image_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt", required=True, help="Image generation/edit prompt")
    parser.add_argument("--output", required=True, type=Path, help="Output image path")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--quality", choices=QUALITY_CHOICES)
    parser.add_argument("--size", help="WIDTHxHEIGHT or auto")
    parser.add_argument(
        "--background", choices=["auto", "opaque", "transparent"]
    )
    parser.add_argument("--format", choices=["png", "jpeg", "webp"], default="png")
    parser.add_argument("--n", type=int, choices=range(1, MAX_IMAGES + 1), default=1)
    parser.add_argument("--overwrite", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate or edit images through the configured TDA proxy"
    )
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--provider", default=DEFAULT_PROVIDER)
    parser.add_argument("--token-env", default="TDA_IMAGE_TOKEN")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate a new image")
    add_common_image_args(generate)

    edit = subparsers.add_parser("edit", help="Edit one or more input images")
    add_common_image_args(edit)
    edit.add_argument(
        "--input", type=Path, action="append", required=True, help="Input image path"
    )
    return parser


def build_payload(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
    }
    if args.n != 1:
        payload["n"] = args.n
    if args.quality:
        payload["quality"] = args.quality
    if args.size:
        if args.size != "auto" and not re.fullmatch(r"[1-9][0-9]*x[1-9][0-9]*", args.size):
            raise TDAImageError("--size must be WIDTHxHEIGHT or auto")
        payload["size"] = args.size
    if args.background:
        payload["background"] = args.background
    if args.format != "png":
        payload["output_format"] = args.format

    if args.command == "edit":
        if not 1 <= len(args.input) <= MAX_IMAGES:
            raise TDAImageError(f"Edit requests require 1 to {MAX_IMAGES} input images")
        payload["images"] = [
            {"image_url": image_to_data_url(path.resolve())} for path in args.input
        ]
        return "images/edits", payload
    return "images/generations", payload


def parameter_warnings(args: argparse.Namespace, response: dict[str, Any]) -> list[str]:
    """Flag proxy-normalized request parameters instead of reporting them as honored."""
    warnings: list[str] = []
    if args.size and args.size != "auto":
        actual_size = response.get("size")
        if isinstance(actual_size, str) and actual_size and actual_size != args.size:
            warnings.append(
                f"requested size {args.size} but endpoint returned {actual_size}"
            )
    if args.quality and args.quality != "auto":
        actual_quality = response.get("quality")
        if isinstance(actual_quality, str) and actual_quality and actual_quality != args.quality:
            warnings.append(
                f"requested quality {args.quality} but endpoint returned {actual_quality}"
            )
    return warnings


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.timeout < 1:
            raise TDAImageError("--timeout must be positive")
        provider = load_provider(args.config.expanduser(), args.provider)
        base_url, token, headers, query_params = resolve_connection(
            provider, args.token_env
        )
        parsed_url = urllib.parse.urlsplit(base_url)
        if parsed_url.scheme not in {"http", "https"}:
            raise TDAImageError("Image API base URL must use http or https")
        if parsed_url.scheme == "http" and parsed_url.hostname not in {
            "127.0.0.1",
            "localhost",
            "::1",
        }:
            print(
                "Warning: the configured image endpoint uses cleartext HTTP; "
                "the bearer token may be exposed in transit.",
                file=sys.stderr,
            )

        path, payload = build_payload(args)
        url = endpoint_url(base_url, path, query_params)
        response = request_json(
            url=url,
            payload=payload,
            token=token,
            extra_headers=headers,
            timeout=args.timeout,
        )
        saved = save_images(
            response,
            output=args.output.expanduser(),
            output_format=args.format,
            token=token,
            timeout=args.timeout,
            overwrite=args.overwrite,
        )
        warnings = parameter_warnings(args, response)
        for warning in warnings:
            print(f"tda-image-generation: warning: {warning}", file=sys.stderr)
        result = {
            "status": "completed",
            "saved_paths": [str(path) for path in saved],
            "revised_prompt": response.get("revised_prompt") or args.prompt,
            "background": response.get("background"),
            "quality": response.get("quality"),
            "size": response.get("size"),
            "warnings": warnings,
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except TDAImageError as exc:
        token = locals().get("token", "")
        base_url = locals().get("base_url", "")
        print(
            f"tda-image-generation: {sanitize(str(exc), token, base_url)}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
