"""Endpoint filter pattern parser.

Supports patterns like:
- "GET /users/*" - Method + path pattern
- "DELETE *" - Method only (all paths)
- "/admin/*" - Path only (all methods)
- "* /health" - Explicit wildcard method
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class FilterType(str, Enum):
    """Type of filter pattern."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass
class FilterPattern:
    """Parsed filter pattern."""

    method: str | None  # None means all methods
    path_pattern: str | None  # None means all paths
    original: str  # Original pattern string

    def matches(self, method: str, path: str) -> bool:
        """Check if this pattern matches the given method and path.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (/users, /users/{id}, etc.)

        Returns:
            True if pattern matches
        """
        # Check method
        if self.method is not None and self.method != "*":
            if method.upper() != self.method.upper():
                return False

        # Check path
        if self.path_pattern is not None and self.path_pattern != "*":
            if not self._path_matches(path):
                return False

        return True

    def _path_matches(self, path: str) -> bool:
        """Check if path matches the pattern using glob-style matching."""
        if self.path_pattern is None:
            return True

        pattern = self.path_pattern

        # Normalize paths
        path = "/" + path.strip("/")
        pattern = "/" + pattern.strip("/")

        # Handle ** for multi-segment matching
        if "**" in pattern:
            # Convert to regex: first escape special chars, then handle wildcards
            # Use placeholder for ** to avoid double-replacement
            regex_pattern = pattern.replace("**", "\x00DOUBLE\x00")
            regex_pattern = regex_pattern.replace("*", "[^/]*")
            regex_pattern = regex_pattern.replace("\x00DOUBLE\x00", ".*")
            regex_pattern = "^" + regex_pattern + "$"
            return bool(re.match(regex_pattern, path))

        # Use fnmatch for simple glob patterns
        return fnmatch.fnmatch(path, pattern)


def parse_pattern(pattern: str) -> FilterPattern:
    """Parse a filter pattern string.

    Supported formats:
    - "METHOD /path" - e.g., "GET /users/*"
    - "METHOD *" - e.g., "DELETE *"
    - "/path" - e.g., "/admin/*"
    - "* /path" - e.g., "* /health"

    Args:
        pattern: Filter pattern string

    Returns:
        Parsed FilterPattern
    """
    pattern = pattern.strip()

    if not pattern:
        raise ValueError("Empty filter pattern")

    # Check if pattern starts with a method
    methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "*"}
    parts = pattern.split(None, 1)  # Split on first whitespace

    if len(parts) == 2 and parts[0].upper() in methods:
        # "METHOD /path" format
        method = parts[0].upper() if parts[0] != "*" else None
        path_pattern = parts[1] if parts[1] != "*" else None
        return FilterPattern(method=method, path_pattern=path_pattern, original=pattern)

    if len(parts) == 1:
        token = parts[0]

        if token.upper() in methods:
            # Just a method like "DELETE"
            method = token.upper() if token != "*" else None
            return FilterPattern(method=method, path_pattern=None, original=pattern)

        if token.startswith("/") or token.startswith("*"):
            # Just a path pattern
            path_pattern = token if token != "*" else None
            return FilterPattern(method=None, path_pattern=path_pattern, original=pattern)

    # Default: treat whole thing as path pattern
    return FilterPattern(method=None, path_pattern=pattern, original=pattern)


def parse_patterns(patterns: Sequence[str]) -> list[FilterPattern]:
    """Parse multiple filter patterns.

    Args:
        patterns: List of pattern strings

    Returns:
        List of parsed FilterPatterns
    """
    return [parse_pattern(p) for p in patterns]


@dataclass
class FilterResult:
    """Result of filtering an operation."""

    included: bool
    matched_by: FilterPattern | None = None


class EndpointFilter:
    """Filter for determining which endpoints to include/exclude."""

    def __init__(
        self,
        include_patterns: Sequence[str] | None = None,
        exclude_patterns: Sequence[str] | None = None,
    ) -> None:
        """Initialize endpoint filter.

        Args:
            include_patterns: Patterns for endpoints to include (if empty, include all)
            exclude_patterns: Patterns for endpoints to exclude
        """
        self._include = parse_patterns(include_patterns or [])
        self._exclude = parse_patterns(exclude_patterns or [])

    def should_include(self, method: str, path: str) -> FilterResult:
        """Determine if an endpoint should be included.

        Logic:
        1. If exclude patterns match, exclude (unless include also matches)
        2. If include patterns exist and none match, exclude
        3. Otherwise include

        Args:
            method: HTTP method
            path: API path

        Returns:
            FilterResult with inclusion decision and matching pattern
        """
        # Check excludes first
        for pattern in self._exclude:
            if pattern.matches(method, path):
                # Check if any include pattern overrides
                for inc_pattern in self._include:
                    if inc_pattern.matches(method, path):
                        return FilterResult(included=True, matched_by=inc_pattern)
                return FilterResult(included=False, matched_by=pattern)

        # If we have include patterns, must match at least one
        if self._include:
            for pattern in self._include:
                if pattern.matches(method, path):
                    return FilterResult(included=True, matched_by=pattern)
            return FilterResult(included=False, matched_by=None)

        # Default: include
        return FilterResult(included=True, matched_by=None)

    def filter_operations(
        self, operations: Sequence[tuple[str, str]]
    ) -> list[tuple[str, str]]:
        """Filter a list of operations.

        Args:
            operations: List of (method, path) tuples

        Returns:
            Filtered list of operations
        """
        return [
            (method, path)
            for method, path in operations
            if self.should_include(method, path).included
        ]
