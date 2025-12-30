"""Tests for plan generation and validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omcp.config.models import (
    LLMNaming,
    LLMOutput,
    LLMPolicy,
    LLMProvider,
    LLMSettings,
    LLMStrategy,
)
from omcp.planner import (
    OMCPPlan,
    PlanDiff,
    PlanPolicy,
    PlanProvenance,
    PlannedModule,
    PlannedTool,
    ValidationError,
    ValidationResult,
    compute_diff,
    diff_summary,
    generate_default_plan,
    raise_if_invalid,
    validate_plan,
)
from omcp.planner.llm import (
    AnthropicAdapter,
    GeminiAdapter,
    LLMAdapter,
    OpenAIAdapter,
    create_llm_adapter,
)
from omcp.planner.prompts import build_plan_prompt, format_operations_table
from omcp.spec import load_spec_sync, normalize_spec
from omcp.utils.errors import PlanGenerationError, PlanValidationError


FIXTURES = Path(__file__).parent / "fixtures"


class TestPlanSchema:
    """Test plan schema models."""

    def test_planned_tool_defaults(self):
        """PlannedTool has correct defaults."""
        tool = PlannedTool(
            operation_id="listPets",
            method="GET",
            path="/pets",
            tool_name="list_pets",
            description="List all pets",
        )
        assert tool.expose is True
        assert tool.module == "default"
        assert tool.safety_notes == []

    def test_planned_tool_with_safety_notes(self):
        """PlannedTool can have safety notes."""
        tool = PlannedTool(
            operation_id="deletePet",
            method="DELETE",
            path="/pets/{id}",
            tool_name="delete_pet",
            description="Delete a pet",
            expose=False,
            safety_notes=["Destructive operation", "Requires admin"],
        )
        assert tool.expose is False
        assert len(tool.safety_notes) == 2

    def test_planned_module(self):
        """PlannedModule creation."""
        module = PlannedModule(
            name="pet_management",
            description="Operations for managing pets",
            policy_overrides={"allow_delete": False},
        )
        assert module.name == "pet_management"
        assert module.policy_overrides == {"allow_delete": False}

    def test_plan_policy_defaults(self):
        """PlanPolicy has correct defaults."""
        policy = PlanPolicy()
        assert policy.block_methods == ["DELETE"]
        assert policy.block_path_patterns == []
        assert policy.require_auth_for_writes is True

    def test_plan_provenance(self):
        """PlanProvenance tracks generation metadata."""
        provenance = PlanProvenance(
            planner_model="gemini-2.0-flash",
            planner_provider="gemini",
            spec_hash="abc123",
        )
        assert provenance.planner_model == "gemini-2.0-flash"
        assert provenance.generated_at is not None

    def test_omcp_plan_complete(self):
        """OMCPPlan assembles all components."""
        plan = OMCPPlan(
            api_name="Pet Store API",
            base_url="https://api.example.com",
            modules=[
                PlannedModule(name="pets", description="Pet operations"),
            ],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List all pets",
                    module="pets",
                ),
                PlannedTool(
                    operation_id="deletePet",
                    method="DELETE",
                    path="/pets/{id}",
                    tool_name="delete_pet",
                    description="Delete a pet",
                    expose=False,
                    module="pets",
                ),
            ],
        )
        assert plan.version == "2.0"
        assert len(plan.tools) == 2

    def test_get_tools_by_module(self):
        """Group tools by module."""
        plan = OMCPPlan(
            api_name="Test API",
            base_url="https://api.example.com",
            modules=[
                PlannedModule(name="users", description="User operations"),
                PlannedModule(name="orders", description="Order operations"),
            ],
            tools=[
                PlannedTool(
                    operation_id="listUsers",
                    method="GET",
                    path="/users",
                    tool_name="list_users",
                    description="List users",
                    module="users",
                ),
                PlannedTool(
                    operation_id="listOrders",
                    method="GET",
                    path="/orders",
                    tool_name="list_orders",
                    description="List orders",
                    module="orders",
                ),
                PlannedTool(
                    operation_id="hidden",
                    method="GET",
                    path="/hidden",
                    tool_name="hidden",
                    description="Hidden",
                    expose=False,
                    module="users",
                ),
            ],
        )

        by_module = plan.get_tools_by_module()
        assert len(by_module["users"]) == 1  # Excludes non-exposed
        assert len(by_module["orders"]) == 1

    def test_get_exposed_tools(self):
        """Get only exposed tools."""
        plan = OMCPPlan(
            api_name="Test API",
            base_url="https://api.example.com",
            tools=[
                PlannedTool(
                    operation_id="exposed",
                    method="GET",
                    path="/exposed",
                    tool_name="exposed_tool",
                    description="Exposed",
                    expose=True,
                ),
                PlannedTool(
                    operation_id="hidden",
                    method="GET",
                    path="/hidden",
                    tool_name="hidden_tool",
                    description="Hidden",
                    expose=False,
                ),
            ],
        )

        exposed = plan.get_exposed_tools()
        assert len(exposed) == 1
        assert exposed[0].operation_id == "exposed"

    def test_get_tool_name_map(self):
        """Get operationId to tool_name mapping."""
        plan = OMCPPlan(
            api_name="Test API",
            base_url="https://api.example.com",
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List pets",
                ),
            ],
        )

        name_map = plan.get_tool_name_map()
        assert name_map["listPets"] == "list_pets"


class TestPrompts:
    """Test prompt generation."""

    def test_format_operations_table(self):
        """Operations are formatted as table."""
        operations = [
            {
                "operation_id": "listPets",
                "method": "GET",
                "path": "/pets",
                "summary": "List all pets",
                "tags": ["pets"],
            },
            {
                "operation_id": "createPet",
                "method": "POST",
                "path": "/pets",
                "summary": "Create a pet",
                "tags": ["pets", "write"],
            },
        ]

        table = format_operations_table(operations)
        assert "| Operation ID |" in table
        assert "| listPets |" in table
        assert "| GET |" in table
        assert "pets, write" in table  # Tags joined

    def test_build_plan_prompt(self):
        """Full prompt is built correctly."""
        operations = [
            {
                "operation_id": "listPets",
                "method": "GET",
                "path": "/pets",
                "summary": "List pets",
                "tags": [],
            },
        ]

        prompt = build_plan_prompt(
            api_name="Pet Store",
            base_url="https://api.example.com",
            operations=operations,
            blocked_methods=["DELETE"],
            blocked_paths=["/admin/**"],
            max_tools=100,
            target_per_module=20,
        )

        assert "Pet Store" in prompt
        assert "https://api.example.com" in prompt
        assert "DELETE" in prompt
        assert "/admin/**" in prompt
        assert "listPets" in prompt

    def test_prompt_truncates_long_summaries(self):
        """Long summaries are truncated in table."""
        operations = [
            {
                "operation_id": "test",
                "method": "GET",
                "path": "/test",
                "summary": "A" * 100,  # Very long summary
                "tags": [],
            },
        ]

        table = format_operations_table(operations)
        # Should be truncated to 50 chars
        assert "A" * 50 in table
        assert "A" * 51 not in table


class TestLLMAdapters:
    """Test LLM adapter creation."""

    def test_create_gemini_adapter(self):
        """Create Gemini adapter from settings."""
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.GEMINI,
            model="gemini-2.0-flash",
            api_key="test-key",
            temperature=0.2,
        )

        adapter = create_llm_adapter(settings)
        assert isinstance(adapter, GeminiAdapter)
        assert adapter.model_name == "gemini-2.0-flash"

    def test_create_openai_adapter(self):
        """Create OpenAI adapter from settings."""
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
            api_key="test-key",
        )

        adapter = create_llm_adapter(settings)
        assert isinstance(adapter, OpenAIAdapter)
        assert adapter.model_name == "gpt-4o-mini"

    def test_create_anthropic_adapter(self):
        """Create Anthropic adapter from settings."""
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.ANTHROPIC,
            model="claude-3-5-sonnet-20241022",
            api_key="test-key",
        )

        adapter = create_llm_adapter(settings)
        assert isinstance(adapter, AnthropicAdapter)
        assert adapter.model_name == "claude-3-5-sonnet-20241022"

    def test_missing_api_key_raises(self):
        """Missing API key raises error."""
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.GEMINI,
            model="gemini-2.0-flash",
            api_key="",  # Empty key
        )

        with pytest.raises(PlanGenerationError) as exc:
            create_llm_adapter(settings)
        assert "API key not configured" in exc.value.message

    def test_unsupported_provider_raises(self):
        """Unsupported provider raises error."""
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.LOCAL,  # Not implemented
            model="local-model",
            api_key="test-key",
        )

        with pytest.raises(PlanGenerationError) as exc:
            create_llm_adapter(settings)
        assert "Unsupported LLM provider" in exc.value.message


class TestValidation:
    """Test plan validation."""

    def _create_test_spec(self):
        """Create a test normalized spec."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        return normalize_spec(spec, "https://api.example.com")

    def _create_test_settings(self):
        """Create test LLM settings."""
        return LLMSettings(
            enabled=True,
            provider=LLMProvider.GEMINI,
            model="gemini-2.0-flash",
            api_key="test-key",
            strategy=LLMStrategy(
                max_tools_total=100,
                max_tools_per_module=50,
                target_tools_per_module=20,
                policy=LLMPolicy(
                    block_methods=["DELETE"],
                    block_path_globs=["/admin/**"],
                ),
            ),
        )

    def test_validate_valid_plan(self):
        """Valid plan passes validation."""
        spec = self._create_test_spec()
        settings = self._create_test_settings()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default module")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List all pets",
                ),
            ],
        )

        result = validate_plan(plan, spec, settings)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_operation(self):
        """Plan with non-existent operation fails."""
        spec = self._create_test_spec()
        settings = self._create_test_settings()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            tools=[
                PlannedTool(
                    operation_id="fakeOperation",  # Doesn't exist
                    method="GET",
                    path="/fake",
                    tool_name="fake_tool",
                    description="Fake tool",
                ),
            ],
        )

        result = validate_plan(plan, spec, settings)
        assert result.valid is False
        assert any(e.code == "INVALID_OPERATION" for e in result.errors)

    def test_validate_duplicate_tool_names(self):
        """Duplicate tool names fail validation."""
        spec = self._create_test_spec()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="same_name",
                    description="Tool 1",
                ),
                PlannedTool(
                    operation_id="getPet",
                    method="GET",
                    path="/pets/{petId}",
                    tool_name="same_name",  # Duplicate!
                    description="Tool 2",
                ),
            ],
        )

        result = validate_plan(plan, spec)
        assert result.valid is False
        assert any(e.code == "DUPLICATE_TOOL_NAME" for e in result.errors)

    def test_validate_duplicate_module_names(self):
        """Duplicate module names fail validation."""
        spec = self._create_test_spec()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[
                PlannedModule(name="pets", description="Module 1"),
                PlannedModule(name="pets", description="Module 2"),  # Duplicate!
            ],
        )

        result = validate_plan(plan, spec)
        assert result.valid is False
        assert any(e.code == "DUPLICATE_MODULE_NAME" for e in result.errors)

    def test_validate_blocked_method(self):
        """Tool using blocked method fails policy check."""
        spec = self._create_test_spec()
        settings = self._create_test_settings()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="deletePet",
                    method="DELETE",  # Blocked by policy
                    path="/pets/{petId}",
                    tool_name="delete_pet",
                    description="Delete a pet",
                    expose=True,  # Still exposed
                ),
            ],
        )

        result = validate_plan(plan, spec, settings)
        assert result.valid is False
        assert any(e.code == "BLOCKED_METHOD" for e in result.errors)

    def test_validate_too_many_tools(self):
        """Plan with too many tools fails size check."""
        spec = self._create_test_spec()
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.GEMINI,
            model="gemini-2.0-flash",
            api_key="test-key",
            strategy=LLMStrategy(
                max_tools_total=1,  # Only allow 1 tool
            ),
        )

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="Tool 1",
                ),
                PlannedTool(
                    operation_id="getPet",
                    method="GET",
                    path="/pets/{petId}",
                    tool_name="get_pet",
                    description="Tool 2",
                ),
            ],
        )

        result = validate_plan(plan, spec, settings)
        assert result.valid is False
        assert any(e.code == "TOO_MANY_TOOLS" for e in result.errors)

    def test_validate_name_too_long(self):
        """Long tool name generates warning."""
        spec = self._create_test_spec()
        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.GEMINI,
            model="gemini-2.0-flash",
            api_key="test-key",
            strategy=LLMStrategy(
                naming=LLMNaming(max_name_length=10),  # Very short
            ),
        )

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_all_pets_in_store",  # Too long
                    description="List pets",
                ),
            ],
        )

        result = validate_plan(plan, spec, settings)
        # Should be a warning, not error
        assert any(w.code == "NAME_TOO_LONG" for w in result.warnings)

    def test_validate_not_snake_case(self):
        """Non-snake_case name generates warning."""
        spec = self._create_test_spec()
        settings = self._create_test_settings()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="listPets",  # camelCase, not snake_case
                    description="List pets",
                ),
            ],
        )

        result = validate_plan(plan, spec, settings)
        assert any(w.code == "NAME_NOT_SNAKE_CASE" for w in result.warnings)

    def test_raise_if_invalid(self):
        """raise_if_invalid raises on invalid result."""
        result = ValidationResult(valid=False)
        result.add_error("TEST_ERROR", "Test error message")

        with pytest.raises(PlanValidationError) as exc:
            raise_if_invalid(result)
        assert "1 error" in exc.value.message

    def test_raise_if_invalid_passes_valid(self):
        """raise_if_invalid does nothing for valid result."""
        result = ValidationResult(valid=True)
        raise_if_invalid(result)  # Should not raise


class TestDiff:
    """Test plan diff computation."""

    def _create_test_spec(self):
        """Create a test normalized spec."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        return normalize_spec(spec, "https://api.example.com")

    def test_compute_diff_renamed_tools(self):
        """Diff detects renamed tools."""
        spec = self._create_test_spec()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_all_pets",  # Different from operationId
                    description="List pets",
                ),
            ],
        )

        diff = compute_diff(plan, spec)
        assert len(diff.renamed_tools) == 1
        assert diff.renamed_tools[0].original_name == "listPets"
        assert diff.renamed_tools[0].new_name == "list_all_pets"

    def test_compute_diff_excluded_tools(self):
        """Diff tracks excluded operations."""
        spec = self._create_test_spec()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List pets",
                    expose=False,  # Excluded
                ),
            ],
        )

        diff = compute_diff(plan, spec)
        assert diff.total_excluded == 1
        assert diff.total_exposed == 0
        assert len(diff.excluded_tools) == 1

    def test_compute_diff_modules(self):
        """Diff tracks module assignments."""
        spec = self._create_test_spec()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[
                PlannedModule(name="pets", description="Pet operations"),
                PlannedModule(name="users", description="User operations"),
            ],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List pets",
                    module="pets",
                ),
            ],
        )

        diff = compute_diff(plan, spec)
        assert "pets" in diff.modules
        assert "users" in diff.modules
        assert diff.tools_per_module.get("pets") == 1

    def test_diff_summary(self):
        """Diff summary is generated."""
        spec = self._create_test_spec()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="default", description="Default")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List pets",
                ),
            ],
        )

        diff = compute_diff(plan, spec)
        summary = diff_summary(diff)
        assert "1/" in summary  # 1/N tools exposed
        assert "exposed" in summary


class TestDefaultPlanGeneration:
    """Test default (non-LLM) plan generation."""

    def test_generate_default_plan(self):
        """Generate a default plan without LLM."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://api.example.com")

        plan = generate_default_plan(normalized, api_name="Test API")

        assert plan.api_name == "Test API"
        assert plan.base_url == "https://api.example.com"
        assert len(plan.tools) == len(normalized.operations)
        assert len(plan.modules) == 1
        assert plan.modules[0].name == "default"

    def test_default_plan_keeps_operation_ids(self):
        """Default plan uses operationIds as tool names."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "")

        plan = generate_default_plan(normalized)

        # Find the listPets operation
        list_pets = next(
            (t for t in plan.tools if t.operation_id == "listPets"),
            None,
        )
        assert list_pets is not None
        assert list_pets.tool_name == "listPets"  # Same as operationId

    def test_default_plan_provenance(self):
        """Default plan has correct provenance."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "")

        plan = generate_default_plan(normalized)

        assert plan.provenance.planner_model == "none"
        assert plan.provenance.planner_provider == "default"
        assert plan.provenance.spec_hash == normalized.content_hash


class TestPlanGeneration:
    """Test LLM-based plan generation with mocked responses."""

    @pytest.mark.asyncio
    async def test_generate_plan_with_mock(self):
        """Generate plan using mocked LLM response."""
        from omcp.planner.generate import generate_plan

        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://api.example.com")

        settings = LLMSettings(
            enabled=True,
            provider=LLMProvider.GEMINI,
            model="gemini-2.0-flash",
            api_key="test-key",
        )

        # Mock response from LLM
        mock_response = json.dumps({
            "modules": [
                {"name": "pet_management", "description": "Pet operations"}
            ],
            "tools": [
                {
                    "operation_id": "listPets",
                    "method": "GET",
                    "path": "/pets",
                    "tool_name": "list_pets",
                    "description": "List all pets with pagination",
                    "expose": True,
                    "module": "pet_management",
                    "safety_notes": [],
                }
            ],
        })

        # Patch the adapter
        with patch("omcp.planner.generate.create_llm_adapter") as mock_create:
            mock_adapter = MagicMock()
            mock_adapter.generate = AsyncMock(return_value=mock_response)
            mock_adapter.model_name = "gemini-2.0-flash"
            mock_create.return_value = mock_adapter

            plan = await generate_plan(normalized, settings, api_name="Test API")

        assert plan.api_name == "Test API"
        assert len(plan.tools) == 1
        assert plan.tools[0].tool_name == "list_pets"
        assert plan.tools[0].module == "pet_management"

    @pytest.mark.asyncio
    async def test_generate_plan_parses_markdown_json(self):
        """Generate plan handles markdown-wrapped JSON."""
        from omcp.planner.generate import _parse_llm_response

        # Markdown code block response
        response = """```json
{
  "modules": [],
  "tools": []
}
```"""

        result = _parse_llm_response(response)
        assert result == {"modules": [], "tools": []}

    @pytest.mark.asyncio
    async def test_generate_plan_invalid_json_raises(self):
        """Invalid JSON response raises error."""
        from omcp.planner.generate import _parse_llm_response

        with pytest.raises(PlanGenerationError) as exc:
            _parse_llm_response("not valid json")
        assert "Failed to parse" in exc.value.message
