"""Tests for OpenAPI spec loading and normalization."""

from pathlib import Path

import pytest

from omcp.spec import load_spec_sync, normalize_spec, validate_spec
from omcp.utils.errors import SpecLoadError, SpecValidationError


FIXTURES = Path(__file__).parent / "fixtures"


class TestSpecLoading:
    """Test OpenAPI spec loading."""

    def test_load_json_spec(self):
        """Load a JSON spec file."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        assert spec["openapi"] == "3.0.0"
        assert spec["info"]["title"] == "Pet Store API"

    def test_load_missing_spec(self):
        """Loading a missing spec raises SpecLoadError."""
        with pytest.raises(SpecLoadError) as exc:
            load_spec_sync(str(FIXTURES / "nonexistent.json"))
        assert "not found" in str(exc.value.message)


class TestSpecValidation:
    """Test OpenAPI spec validation."""

    def test_validate_valid_spec(self):
        """Valid spec passes validation."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        validate_spec(spec)  # Should not raise

    def test_validate_missing_openapi(self):
        """Spec without openapi version fails."""
        with pytest.raises(SpecValidationError):
            validate_spec({"info": {"title": "Test", "version": "1.0"}, "paths": {}})

    def test_validate_missing_paths(self):
        """Spec without paths fails."""
        with pytest.raises(SpecValidationError):
            validate_spec({"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}})

    def test_validate_empty_paths(self):
        """Spec with empty paths fails."""
        with pytest.raises(SpecValidationError):
            validate_spec(
                {"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}, "paths": {}}
            )


class TestSpecNormalization:
    """Test OpenAPI spec normalization."""

    def test_normalize_spec(self):
        """Normalize a spec and get operation index."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://custom.example.com")

        assert normalized.title == "Pet Store API"
        assert normalized.base_url == "https://custom.example.com"
        assert len(normalized.operations) == 5  # 4 operations with IDs + 1 without

    def test_normalize_generates_operation_ids(self):
        """Operations without IDs get generated ones."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "")

        # Find the operation that had no ID (GET /users)
        users_op = next(op for op in normalized.operations if op.path == "/users")
        assert users_op.operation_id == "get_users"

    def test_normalize_extracts_parameters(self):
        """Operation parameters are extracted."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "")

        list_pets = next(op for op in normalized.operations if op.operation_id == "listPets")
        assert "limit" in list_pets.parameters

    def test_normalize_detects_request_body(self):
        """Request bodies are detected."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "")

        create_pet = next(op for op in normalized.operations if op.operation_id == "createPet")
        assert create_pet.has_request_body is True

        list_pets = next(op for op in normalized.operations if op.operation_id == "listPets")
        assert list_pets.has_request_body is False

    def test_normalize_uses_config_base_url(self):
        """Config base_url takes precedence over spec servers."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))

        # With config URL
        normalized = normalize_spec(spec, "https://override.example.com")
        assert normalized.base_url == "https://override.example.com"

        # Without config URL, falls back to spec
        normalized = normalize_spec(spec, "")
        assert normalized.base_url == "https://petstore.example.com/v1"

    def test_normalize_content_hash_stable(self):
        """Content hash is stable across runs."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))

        normalized1 = normalize_spec(spec, "https://example.com")
        normalized2 = normalize_spec(spec, "https://example.com")

        assert normalized1.content_hash == normalized2.content_hash
