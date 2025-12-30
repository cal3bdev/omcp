"""OpenAPI specification normalizer.

Produces a canonical, planner-friendly snapshot of an OpenAPI spec.
Output is deterministic and stable across runs for the same input.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field


class OperationInfo(BaseModel):
    """Metadata for a single API operation."""

    operation_id: str
    method: str
    path: str
    summary: str
    description: str
    tags: list[str] = Field(default_factory=list)
    parameters: list[str] = Field(default_factory=list)  # Parameter names
    has_request_body: bool = False
    deprecated: bool = False


class NormalizedSpec(BaseModel):
    """Normalized OpenAPI specification with operation index."""

    # Original spec info
    title: str
    version: str
    openapi_version: str

    # Resolved base URL
    base_url: str

    # The full normalized spec (with refs resolved where possible)
    spec: dict[str, Any]

    # Operation index for planner
    operations: list[OperationInfo]

    # Hash for cache/determinism checks
    content_hash: str


def normalize_spec(spec: dict[str, Any], base_url: str) -> NormalizedSpec:
    """Normalize an OpenAPI spec for planner consumption.

    Args:
        spec: Raw parsed OpenAPI specification
        base_url: Base URL from config (takes precedence over spec servers)

    Returns:
        NormalizedSpec with resolved refs, stable operation IDs, and index
    """
    # Make a deep copy to avoid mutating the original
    import copy

    normalized = copy.deepcopy(spec)

    # Resolve base URL
    resolved_base_url = _resolve_base_url(normalized, base_url)

    # Ensure all operations have stable IDs
    _ensure_operation_ids(normalized)

    # Resolve $ref where possible (inline simple refs)
    _resolve_refs(normalized)

    # Build operation index
    operations = _build_operation_index(normalized)

    # Compute content hash for determinism
    content_hash = _compute_hash(normalized)

    # Extract metadata
    info = normalized.get("info", {})
    openapi_version = normalized.get("openapi") or normalized.get("swagger", "unknown")

    return NormalizedSpec(
        title=info.get("title", "Untitled API"),
        version=info.get("version", "0.0.0"),
        openapi_version=openapi_version,
        base_url=resolved_base_url,
        spec=normalized,
        operations=operations,
        content_hash=content_hash,
    )


def _resolve_base_url(spec: dict[str, Any], config_base_url: str) -> str:
    """Resolve the base URL, preferring config over spec servers."""
    if config_base_url:
        return config_base_url.rstrip("/")

    # Fall back to first server in spec
    servers = spec.get("servers", [])
    if servers and isinstance(servers, list) and len(servers) > 0:
        url = servers[0].get("url", "")
        if url:
            return url.rstrip("/")

    # OpenAPI 2.0 style
    if "host" in spec:
        scheme = spec.get("schemes", ["https"])[0]
        host = spec["host"]
        base_path = spec.get("basePath", "")
        return f"{scheme}://{host}{base_path}".rstrip("/")

    return ""


def _ensure_operation_ids(spec: dict[str, Any]) -> None:
    """Ensure every operation has a stable operationId."""
    paths = spec.get("paths", {})
    seen_ids: set[str] = set()

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            if not isinstance(operation, dict):
                continue

            existing_id = operation.get("operationId")

            if existing_id and existing_id not in seen_ids:
                seen_ids.add(existing_id)
                continue

            # Generate deterministic ID from method + path
            generated_id = _generate_operation_id(method, path)

            # Handle collisions
            final_id = generated_id
            counter = 2
            while final_id in seen_ids:
                final_id = f"{generated_id}_{counter}"
                counter += 1

            operation["operationId"] = final_id
            seen_ids.add(final_id)


def _generate_operation_id(method: str, path: str) -> str:
    """Generate a deterministic operationId from method and path."""
    # Convert path to snake_case identifier
    # /users/{userId}/posts -> users_userId_posts
    clean_path = path.strip("/")
    clean_path = re.sub(r"\{([^}]+)\}", r"\1", clean_path)  # Remove braces
    clean_path = re.sub(r"[^a-zA-Z0-9]+", "_", clean_path)  # Replace non-alphanum
    clean_path = clean_path.strip("_")

    return f"{method}_{clean_path}" if clean_path else method


def _resolve_refs(spec: dict[str, Any]) -> None:
    """Resolve simple $ref references inline.

    Only resolves refs to components/schemas for now.
    Complex circular refs are left as-is.
    """
    components = spec.get("components", {})
    schemas = components.get("schemas", {})

    # Also support OpenAPI 2.0 definitions
    definitions = spec.get("definitions", {})
    all_defs = {**definitions, **schemas}

    if not all_defs:
        return

    # Simple inline resolution for non-circular refs
    # This is a basic implementation - full resolution would need cycle detection
    _resolve_refs_recursive(spec, all_defs, max_depth=10)


def _resolve_refs_recursive(
    obj: Any, definitions: dict[str, Any], max_depth: int, depth: int = 0
) -> Any:
    """Recursively resolve $ref in an object."""
    if depth >= max_depth:
        return obj

    if isinstance(obj, dict):
        if "$ref" in obj and len(obj) == 1:
            ref = obj["$ref"]
            resolved = _resolve_single_ref(ref, definitions)
            if resolved is not None:
                return _resolve_refs_recursive(resolved, definitions, max_depth, depth + 1)
            return obj

        return {
            k: _resolve_refs_recursive(v, definitions, max_depth, depth)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [_resolve_refs_recursive(item, definitions, max_depth, depth) for item in obj]

    return obj


def _resolve_single_ref(ref: str, definitions: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a single $ref string to its definition."""
    # Handle #/components/schemas/Name or #/definitions/Name
    if ref.startswith("#/components/schemas/"):
        name = ref[len("#/components/schemas/") :]
        return definitions.get(name)
    if ref.startswith("#/definitions/"):
        name = ref[len("#/definitions/") :]
        return definitions.get(name)
    return None


def _build_operation_index(spec: dict[str, Any]) -> list[OperationInfo]:
    """Build an index of all operations for the planner."""
    operations: list[OperationInfo] = []
    paths = spec.get("paths", {})

    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue

        for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
            if method not in path_item:
                continue

            operation = path_item[method]
            if not isinstance(operation, dict):
                continue

            # Extract parameter names
            params = operation.get("parameters", [])
            param_names = [p.get("name", "") for p in params if isinstance(p, dict)]

            # Check for request body
            has_body = "requestBody" in operation or any(
                p.get("in") == "body" for p in params if isinstance(p, dict)
            )

            op_info = OperationInfo(
                operation_id=operation.get("operationId", ""),
                method=method.upper(),
                path=path,
                summary=operation.get("summary", ""),
                description=operation.get("description", ""),
                tags=operation.get("tags", []),
                parameters=param_names,
                has_request_body=has_body,
                deprecated=operation.get("deprecated", False),
            )
            operations.append(op_info)

    return operations


def _compute_hash(spec: dict[str, Any]) -> str:
    """Compute a stable hash of the normalized spec."""
    import json

    # Sort keys for deterministic output
    content = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()[:16]
