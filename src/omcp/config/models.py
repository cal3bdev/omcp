"""Pydantic configuration models for OMCP."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Mode(str, Enum):
    """Server mode."""

    SINGLE = "single"
    MODULAR = "modular"


class AuthType(str, Enum):
    """Authentication type."""

    NONE = "none"
    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"


class LLMProvider(str, Enum):
    """LLM provider."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    LOCAL = "local"


# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------


class AuthConfig(BaseModel):
    """Authentication configuration."""

    type: AuthType
    # API key / Bearer
    token: str | None = None
    key: str | None = None
    header_name: str = "Authorization"
    # OAuth2
    client_id: str | None = None
    client_secret: str | None = None
    auth_url: str | None = None
    token_url: str | None = None
    scopes: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# LLM Planner
# -----------------------------------------------------------------------------


class LLMNaming(BaseModel):
    """Naming style constraints for LLM planner."""

    style: str = "verb_noun"
    avoid: list[str] = Field(default_factory=list)
    include_resource_in_name: bool = True
    max_name_length: int = 40


class LLMPolicy(BaseModel):
    """Safety policy constraints for LLM planner."""

    block_methods: list[str] = Field(default_factory=lambda: ["DELETE"])
    block_path_globs: list[str] = Field(default_factory=list)
    require_auth_for_non_get: bool = True
    pii_redaction: bool = True


class LLMStrategy(BaseModel):
    """LLM planning strategy configuration."""

    objectives: list[str] = Field(
        default_factory=lambda: [
            "minimize_tool_surface",
            "agent_friendly_naming",
            "high_signal_descriptions",
            "safe_by_default",
            "cohesive_modules",
        ]
    )
    max_tools_total: int = 200
    target_tools_per_module: int = 40
    max_tools_per_module: int = 80
    naming: LLMNaming = Field(default_factory=LLMNaming)
    policy: LLMPolicy = Field(default_factory=LLMPolicy)


class LLMPrompts(BaseModel):
    """LLM prompt template configuration."""

    system: str = "omcp/planner/system_prompt_v2"
    plan: str = "omcp/planner/plan_prompt_v2"


class LLMOutput(BaseModel):
    """LLM output configuration."""

    plan_path: str = "./omcp.plan.json"
    save_normalized_spec: bool = True
    normalized_spec_path: str = "./.omcp/spec.normalized.json"


class LLMSettings(BaseModel):
    """LLM planner configuration."""

    enabled: bool = False
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 5000
    strategy: LLMStrategy = Field(default_factory=LLMStrategy)
    prompts: LLMPrompts = Field(default_factory=LLMPrompts)
    output: LLMOutput = Field(default_factory=LLMOutput)


# -----------------------------------------------------------------------------
# Modules (Micro-MCPs)
# -----------------------------------------------------------------------------


class ModuleRuntime(BaseModel):
    """Module runtime configuration."""

    base_port: int = 9100
    host: str = "127.0.0.1"
    transport: str = "http"


class ModulesSettings(BaseModel):
    """Modules configuration."""

    enabled: bool = False
    split_strategy: str = "llm"  # llm | tags | path | hybrid
    allow: list[str] = Field(default_factory=lambda: ["*"])
    deny: list[str] = Field(default_factory=list)
    runtime: ModuleRuntime = Field(default_factory=ModuleRuntime)


# -----------------------------------------------------------------------------
# Hub
# -----------------------------------------------------------------------------


class HubRouting(BaseModel):
    """Hub routing configuration."""

    mode: str = "tool_to_module"
    enforce_policy: bool = True


class HubDiscovery(BaseModel):
    """Hub discovery configuration."""

    expose_registry_tool: bool = True
    expose_module_docs_resource: bool = True


class HubSettings(BaseModel):
    """Hub server configuration."""

    enabled: bool = False
    name: str = "OMCP Hub"
    transport: str = "http"
    host: str = "127.0.0.1"
    port: int = 9000
    routing: HubRouting = Field(default_factory=HubRouting)
    discovery: HubDiscovery = Field(default_factory=HubDiscovery)


# -----------------------------------------------------------------------------
# Endpoint Filtering
# -----------------------------------------------------------------------------


class EndpointsConfig(BaseModel):
    """Endpoint include/exclude patterns."""

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Tool Customization
# -----------------------------------------------------------------------------


class ToolOverride(BaseModel):
    """Per-tool customization."""

    name: str | None = None
    description: str | None = None


# -----------------------------------------------------------------------------
# Server Settings
# -----------------------------------------------------------------------------


class ServerSettings(BaseModel):
    """Server configuration."""

    timeout: int = 60
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000


# -----------------------------------------------------------------------------
# Advanced Settings
# -----------------------------------------------------------------------------


class RetrySettings(BaseModel):
    """HTTP retry configuration."""

    max_attempts: int = 3
    backoff_factor: float = 0.5


class ResponseSettings(BaseModel):
    """Response handling configuration."""

    max_size_mb: int = 10
    truncate_arrays: int = 100


class AdvancedSettings(BaseModel):
    """Advanced configuration options."""

    headers: dict[str, str] = Field(default_factory=dict)
    retry: RetrySettings = Field(default_factory=RetrySettings)
    response: ResponseSettings = Field(default_factory=ResponseSettings)


# -----------------------------------------------------------------------------
# Root Configuration
# -----------------------------------------------------------------------------


class OMCPConfig(BaseModel):
    """Root OMCP configuration."""

    # Required
    name: str
    spec: str
    base_url: str
    auth: AuthConfig

    # Mode
    mode: Mode = Mode.SINGLE

    # Optional sections
    llm: LLMSettings = Field(default_factory=LLMSettings)
    modules: ModulesSettings = Field(default_factory=ModulesSettings)
    hub: HubSettings = Field(default_factory=HubSettings)
    endpoints: EndpointsConfig = Field(default_factory=EndpointsConfig)
    tools: dict[str, ToolOverride] = Field(default_factory=dict)
    server: ServerSettings = Field(default_factory=ServerSettings)
    advanced: AdvancedSettings = Field(default_factory=AdvancedSettings)

    model_config = {"extra": "forbid"}
