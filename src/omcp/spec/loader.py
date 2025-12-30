"""OpenAPI specification loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import yaml

from omcp.utils.errors import SpecLoadError


async def load_spec(source: str) -> dict[str, Any]:
    """Load an OpenAPI specification from a file or URL.

    Args:
        source: File path or URL to the OpenAPI spec

    Returns:
        Parsed OpenAPI specification as a dict

    Raises:
        SpecLoadError: If the spec cannot be loaded or parsed
    """
    if _is_url(source):
        return await _load_from_url(source)
    return _load_from_file(source)


def load_spec_sync(source: str) -> dict[str, Any]:
    """Synchronous version of load_spec."""
    if _is_url(source):
        return _load_from_url_sync(source)
    return _load_from_file(source)


def _is_url(source: str) -> bool:
    """Check if the source is a URL."""
    return source.startswith(("http://", "https://"))


def _load_from_file(path: str) -> dict[str, Any]:
    """Load spec from a local file."""
    file_path = Path(path)

    if not file_path.exists():
        raise SpecLoadError(f"Spec file not found: {path}")

    try:
        content = file_path.read_text()
    except OSError as e:
        raise SpecLoadError(f"Failed to read spec file: {path}", details=str(e))

    return _parse_spec(content, path)


async def _load_from_url(url: str) -> dict[str, Any]:
    """Load spec from a URL (async)."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            content = response.text
    except httpx.HTTPError as e:
        raise SpecLoadError(f"Failed to fetch spec from URL: {url}", details=str(e))

    return _parse_spec(content, url)


def _load_from_url_sync(url: str) -> dict[str, Any]:
    """Load spec from a URL (sync)."""
    try:
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()
            content = response.text
    except httpx.HTTPError as e:
        raise SpecLoadError(f"Failed to fetch spec from URL: {url}", details=str(e))

    return _parse_spec(content, url)


def _parse_spec(content: str, source: str) -> dict[str, Any]:
    """Parse spec content as JSON or YAML."""
    # Try JSON first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try YAML
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return data
        raise SpecLoadError(
            f"Spec must be a JSON/YAML object, got {type(data).__name__}",
            details=f"Source: {source}",
        )
    except yaml.YAMLError as e:
        raise SpecLoadError(f"Failed to parse spec as JSON or YAML", details=str(e))
