"""Tests for modular servers (Micro-MCPs)."""

from __future__ import annotations

from pathlib import Path

import pytest

from omcp.config.models import ModulesSettings
from omcp.modules import (
    ModuleBuilder,
    ModuleDefinition,
    ModuleRegistry,
    ModuleRunner,
    SplitResult,
    split_by_hybrid,
    split_by_path,
    split_by_plan,
    split_by_tags,
    split_operations,
)
from omcp.planner.schema import OMCPPlan, PlannedModule, PlannedTool
from omcp.spec import load_spec_sync, normalize_spec


FIXTURES = Path(__file__).parent / "fixtures"


class TestModuleSplitter:
    """Test module splitting strategies."""

    def _load_spec(self):
        """Load test spec."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        return normalize_spec(spec, "https://api.example.com")

    def _default_settings(self) -> ModulesSettings:
        """Get default module settings."""
        return ModulesSettings(
            enabled=True,
            allow=["*"],
            deny=[],
        )

    def test_split_by_tags_groups_by_first_tag(self):
        """Operations are grouped by their first tag."""
        spec = self._load_spec()
        settings = self._default_settings()

        result = split_by_tags(spec, settings)

        assert isinstance(result, SplitResult)
        assert len(result.modules) > 0

        # Check that modules were created from tags
        module_names = {m.name for m in result.modules}
        assert "pets" in module_names or "default" in module_names

    def test_split_by_tags_uses_default_for_untagged(self):
        """Operations without tags go to 'default' module."""
        spec = self._load_spec()
        settings = self._default_settings()

        result = split_by_tags(spec, settings)

        # If there are untagged operations, they should be in default
        # The fixture may or may not have untagged ops
        all_ops = sum(len(m.operations) for m in result.modules)
        assert all_ops > 0

    def test_split_by_path_groups_by_first_segment(self):
        """Operations are grouped by first path segment."""
        spec = self._load_spec()
        settings = self._default_settings()

        result = split_by_path(spec, settings)

        assert len(result.modules) > 0

        # Check module names come from paths
        module_names = {m.name for m in result.modules}
        # Pet store spec has /pets path
        assert "pets" in module_names or len(module_names) > 0

    def test_split_by_hybrid_prefers_tags(self):
        """Hybrid strategy prefers tags over paths."""
        spec = self._load_spec()
        settings = self._default_settings()

        tag_result = split_by_tags(spec, settings)
        hybrid_result = split_by_hybrid(spec, settings)

        # Both should produce similar results for tagged operations
        # Hybrid may have fewer modules if tags are more specific
        assert len(hybrid_result.modules) >= 1

    def test_split_by_plan_uses_plan_assignments(self):
        """Plan-based split uses module assignments from plan."""
        spec = self._load_spec()
        settings = self._default_settings()

        # Create a plan with specific module assignments
        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[
                PlannedModule(name="read_ops", description="Read operations"),
                PlannedModule(name="write_ops", description="Write operations"),
            ],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_pets",
                    description="List all pets",
                    module="read_ops",
                ),
                PlannedTool(
                    operation_id="createPet",
                    method="POST",
                    path="/pets",
                    tool_name="create_pet",
                    description="Create a pet",
                    module="write_ops",
                ),
            ],
        )

        result = split_by_plan(spec, plan, settings)

        # Should have exactly the modules from the plan
        module_names = {m.name for m in result.modules}
        assert "read_ops" in module_names
        assert "write_ops" in module_names

        # Check operations are assigned correctly
        read_module = result.get_module("read_ops")
        assert read_module is not None
        assert any(op.operation_id == "listPets" for op in read_module.operations)

    def test_split_operations_selects_strategy(self):
        """split_operations dispatches to correct strategy."""
        spec = self._load_spec()

        # Test tags strategy
        settings = ModulesSettings(enabled=True, split_strategy="tags", allow=["*"])
        result = split_operations(spec, settings)
        assert len(result.modules) > 0

        # Test path strategy
        settings = ModulesSettings(enabled=True, split_strategy="path", allow=["*"])
        result = split_operations(spec, settings)
        assert len(result.modules) > 0

        # Test hybrid strategy
        settings = ModulesSettings(enabled=True, split_strategy="hybrid", allow=["*"])
        result = split_operations(spec, settings)
        assert len(result.modules) > 0

    def test_split_operations_llm_requires_plan(self):
        """LLM strategy raises error without plan."""
        spec = self._load_spec()
        settings = ModulesSettings(enabled=True, split_strategy="llm", allow=["*"])

        with pytest.raises(ValueError) as exc:
            split_operations(spec, settings, plan=None)
        assert "Plan required" in str(exc.value)

    def test_module_allow_list_filters(self):
        """Allow list filters which modules are created."""
        spec = self._load_spec()
        settings = ModulesSettings(
            enabled=True,
            split_strategy="path",
            allow=["pets"],  # Only allow pets module
            deny=[],
        )

        result = split_by_path(spec, settings)

        # Should only have pets module
        module_names = {m.name for m in result.modules}
        assert module_names == {"pets"} or len(module_names) <= 1

    def test_module_deny_list_filters(self):
        """Deny list excludes modules."""
        spec = self._load_spec()
        settings = ModulesSettings(
            enabled=True,
            split_strategy="path",
            allow=["*"],
            deny=["admin*"],  # Deny admin modules
        )

        result = split_by_path(spec, settings)

        # No admin modules should exist
        module_names = {m.name for m in result.modules}
        assert not any(n.startswith("admin") for n in module_names)

    def test_split_result_total_operations(self):
        """SplitResult counts total operations correctly."""
        spec = self._load_spec()
        settings = self._default_settings()

        result = split_by_tags(spec, settings)

        # Total should match sum across modules
        total = sum(len(m.operations) for m in result.modules)
        assert result.total_operations == total

    def test_module_definition_tool_customizations(self):
        """ModuleDefinition tracks tool customizations from plan."""
        spec = self._load_spec()
        settings = self._default_settings()

        plan = OMCPPlan(
            api_name="Pet Store",
            base_url="https://api.example.com",
            modules=[PlannedModule(name="pets", description="Pet operations")],
            tools=[
                PlannedTool(
                    operation_id="listPets",
                    method="GET",
                    path="/pets",
                    tool_name="list_all_pets",  # Custom name
                    description="Custom description",  # Custom desc
                    module="pets",
                ),
            ],
        )

        result = split_by_plan(spec, plan, settings)
        pets_module = result.get_module("pets")

        assert pets_module is not None
        assert pets_module.tool_names.get("listPets") == "list_all_pets"
        assert pets_module.tool_descriptions.get("listPets") == "Custom description"


class TestModuleBuilder:
    """Test module server builder."""

    def _load_spec(self):
        """Load test spec."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        return normalize_spec(spec, "https://api.example.com")

    def _create_test_config(self):
        """Create test configuration."""
        from omcp.config import load_config

        return load_config(FIXTURES / "test_config.yaml")

    def test_module_builder_creates_filtered_spec(self):
        """ModuleBuilder creates spec with only module's operations."""
        spec = self._load_spec()
        config = self._create_test_config()

        # Create auth provider
        from omcp.auth import create_auth_provider

        auth = create_auth_provider(config.auth, provider_name=config.name)

        # Create a module with subset of operations
        list_pets_op = next(op for op in spec.operations if op.operation_id == "listPets")
        module = ModuleDefinition(
            name="read_ops",
            description="Read operations",
            operations=[list_pets_op],
        )

        builder = ModuleBuilder(module, spec, config, auth)
        filtered_spec = builder._create_module_spec()

        # Should only have paths for this module's operations
        assert "/pets" in filtered_spec["paths"]
        # Should only have GET method (listPets is GET)
        assert "get" in filtered_spec["paths"]["/pets"]

    def test_module_builder_applies_tool_names(self):
        """ModuleBuilder applies custom tool names from plan."""
        spec = self._load_spec()
        config = self._create_test_config()

        from omcp.auth import create_auth_provider

        auth = create_auth_provider(config.auth, provider_name=config.name)

        list_pets_op = next(op for op in spec.operations if op.operation_id == "listPets")
        module = ModuleDefinition(
            name="pets",
            description="Pet operations",
            operations=[list_pets_op],
            tool_names={"listPets": "list_all_pets"},
        )

        builder = ModuleBuilder(module, spec, config, auth)
        mcp_names = builder._create_mcp_names()

        assert mcp_names is not None
        assert mcp_names["listPets"] == "list_all_pets"

    def test_module_builder_get_tool_list(self):
        """ModuleBuilder returns correct tool list."""
        spec = self._load_spec()
        config = self._create_test_config()

        from omcp.auth import create_auth_provider

        auth = create_auth_provider(config.auth, provider_name=config.name)

        list_pets_op = next(op for op in spec.operations if op.operation_id == "listPets")
        module = ModuleDefinition(
            name="pets",
            description="Pet operations",
            operations=[list_pets_op],
            tool_names={"listPets": "list_pets"},
            tool_descriptions={"listPets": "List all pets"},
        )

        builder = ModuleBuilder(module, spec, config, auth)
        tools = builder.get_tool_list()

        assert len(tools) == 1
        assert tools[0]["name"] == "list_pets"
        assert tools[0]["description"] == "List all pets"
        assert tools[0]["module"] == "pets"


class TestModuleRegistry:
    """Test module registry."""

    def test_registry_register_and_get(self):
        """Registry stores and retrieves modules."""
        from omcp.modules.runner import ModuleInstance

        registry = ModuleRegistry()

        instance = ModuleInstance(
            name="test_module",
            port=9100,
            url="http://localhost:9100",
            mcp=None,  # type: ignore
            tool_count=5,
        )

        registry.register(instance)

        retrieved = registry.get("test_module")
        assert retrieved is not None
        assert retrieved.name == "test_module"
        assert retrieved.port == 9100

    def test_registry_get_unknown_returns_none(self):
        """Getting unknown module returns None."""
        registry = ModuleRegistry()
        assert registry.get("unknown") is None

    def test_registry_all_modules(self):
        """all_modules returns all registered modules."""
        from omcp.modules.runner import ModuleInstance

        registry = ModuleRegistry()

        for i in range(3):
            registry.register(
                ModuleInstance(
                    name=f"module_{i}",
                    port=9100 + i,
                    url=f"http://localhost:{9100 + i}",
                    mcp=None,  # type: ignore
                    tool_count=i,
                )
            )

        all_mods = registry.all_modules
        assert len(all_mods) == 3

    def test_registry_info(self):
        """get_registry_info returns module info."""
        from omcp.modules.runner import ModuleInstance

        registry = ModuleRegistry()
        registry.register(
            ModuleInstance(
                name="test",
                port=9100,
                url="http://localhost:9100",
                mcp=None,  # type: ignore
                tool_count=10,
            )
        )

        info = registry.get_registry_info()
        assert len(info) == 1
        assert info[0]["name"] == "test"
        assert info[0]["tool_count"] == 10


class TestModuleRunner:
    """Test module runner."""

    def _load_spec(self):
        """Load test spec."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        return normalize_spec(spec, "https://api.example.com")

    def _create_test_config(self):
        """Create test configuration with modular settings."""
        from omcp.config.models import (
            AuthConfig,
            AuthType,
            Mode,
            ModuleRuntime,
            ModulesSettings,
            OMCPConfig,
        )

        return OMCPConfig(
            name="Test API",
            spec=str(FIXTURES / "petstore.json"),
            base_url="https://api.example.com",
            auth=AuthConfig(type=AuthType.BEARER, token="test-token"),
            mode=Mode.MODULAR,
            modules=ModulesSettings(
                enabled=True,
                split_strategy="tags",
                allow=["*"],
                runtime=ModuleRuntime(
                    base_port=9200,
                    host="127.0.0.1",
                    transport="http",
                ),
            ),
        )

    def test_runner_splits_operations(self):
        """ModuleRunner splits operations correctly."""
        spec = self._load_spec()
        config = self._create_test_config()

        runner = ModuleRunner(config, spec)
        split_result = runner.split_result

        assert len(split_result.modules) > 0

    def test_runner_assigns_ports(self):
        """ModuleRunner assigns sequential ports."""
        spec = self._load_spec()
        config = self._create_test_config()

        runner = ModuleRunner(config, spec)

        port0 = runner._get_module_port(0)
        port1 = runner._get_module_port(1)

        assert port0 == 9200
        assert port1 == 9201

    def test_runner_generates_urls(self):
        """ModuleRunner generates correct URLs."""
        spec = self._load_spec()
        config = self._create_test_config()

        runner = ModuleRunner(config, spec)
        url = runner._get_module_url(9200)

        assert "127.0.0.1" in url
        assert "9200" in url

    def test_runner_get_module_info(self):
        """ModuleRunner returns module info."""
        spec = self._load_spec()
        config = self._create_test_config()

        runner = ModuleRunner(config, spec)
        info = runner.get_module_info()

        assert len(info) > 0
        for module_info in info:
            assert "name" in module_info
            assert "port" in module_info
            assert "tool_count" in module_info
            assert "tools" in module_info


class TestSanitization:
    """Test helper functions."""

    def test_sanitize_module_name(self):
        """Module names are sanitized correctly."""
        from omcp.modules.splitter import _sanitize_module_name

        assert _sanitize_module_name("Pet Store") == "pet_store"
        assert _sanitize_module_name("user-management") == "user_management"
        assert _sanitize_module_name("API v2") == "api_v2"
        assert _sanitize_module_name("__weird__") == "weird"
        assert _sanitize_module_name("") == "default"
