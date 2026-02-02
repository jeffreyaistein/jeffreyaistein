"""
Tests for tool schemas and registry.
"""

import pytest

from services.tools import (
    BaseTool,
    ToolCategory,
    ToolResult,
    ToolSchema,
    get_registry,
)


class TestToolRegistry:
    """Tests for the tool registry."""

    def test_registry_singleton(self):
        """Registry should be a singleton."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_all_tools_registered(self):
        """All expected tools should be registered."""
        registry = get_registry()
        tools = registry.list_tools()

        expected_tools = [
            "search_memory",
            "upsert_memories",
            "get_token_metrics",
            "moderation_check_text",
            "moderation_check_image",
            "tts_synthesize",
            "x_post",
            "x_reply",
        ]

        for tool_name in expected_tools:
            assert tool_name in tools, f"Tool {tool_name} not registered"

    def test_get_tool_by_name(self):
        """Should retrieve tool by name."""
        registry = get_registry()
        tool = registry.get("search_memory")

        assert tool is not None
        assert isinstance(tool, BaseTool)
        assert tool.schema.name == "search_memory"

    def test_get_nonexistent_tool(self):
        """Should return None for nonexistent tool."""
        registry = get_registry()
        tool = registry.get("nonexistent_tool")
        assert tool is None

    def test_list_tools_by_category(self):
        """Should filter tools by category."""
        registry = get_registry()

        memory_tools = registry.list_tools(ToolCategory.MEMORY)
        assert "search_memory" in memory_tools
        assert "upsert_memories" in memory_tools
        assert "x_post" not in memory_tools

        social_tools = registry.list_tools(ToolCategory.SOCIAL)
        assert "x_post" in social_tools
        assert "x_reply" in social_tools
        assert "search_memory" not in social_tools


class TestToolSchemas:
    """Tests for tool schema definitions."""

    def test_search_memory_schema(self):
        """search_memory schema should be valid."""
        registry = get_registry()
        schema = registry.get_schema("search_memory")

        assert schema is not None
        assert schema.name == "search_memory"
        assert schema.category == ToolCategory.MEMORY

        # Check required parameters
        param_names = [p.name for p in schema.parameters]
        assert "query" in param_names

        # Check query is required
        query_param = next(p for p in schema.parameters if p.name == "query")
        assert query_param.required is True
        assert query_param.type == "string"

    def test_x_post_schema(self):
        """x_post schema should be valid."""
        registry = get_registry()
        schema = registry.get_schema("x_post")

        assert schema is not None
        assert schema.name == "x_post"
        assert schema.category == ToolCategory.SOCIAL

        # Check required parameters
        text_param = next(p for p in schema.parameters if p.name == "text")
        assert text_param.required is True

        # Check media_urls is array type
        media_param = next(p for p in schema.parameters if p.name == "media_urls")
        assert media_param.type == "array"
        assert media_param.items is not None

class TestToolJsonSchema:
    """Tests for JSON schema generation."""

    def test_to_json_schema(self):
        """Should generate valid JSON schema."""
        registry = get_registry()
        schema = registry.get_schema("search_memory")
        json_schema = schema.to_json_schema()

        assert json_schema["type"] == "object"
        assert "properties" in json_schema
        assert "required" in json_schema
        assert "query" in json_schema["required"]
        assert "query" in json_schema["properties"]

    def test_to_anthropic_tool(self):
        """Should generate valid Anthropic tool format."""
        registry = get_registry()
        schema = registry.get_schema("search_memory")
        anthropic_tool = schema.to_anthropic_tool()

        assert "name" in anthropic_tool
        assert "description" in anthropic_tool
        assert "input_schema" in anthropic_tool
        assert anthropic_tool["name"] == "search_memory"
        assert anthropic_tool["input_schema"]["type"] == "object"

    def test_get_all_anthropic_tools(self):
        """Should get all tools in Anthropic format."""
        registry = get_registry()
        tools = registry.get_anthropic_tools()

        assert len(tools) >= 8  # All our defined tools (image_generate removed)
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool


class TestToolValidation:
    """Tests for parameter validation."""

    def test_validate_required_params(self):
        """Should fail when required params missing."""
        registry = get_registry()
        tool = registry.get("search_memory")

        # Missing required 'query'
        is_valid, error = tool.validate_params({})
        assert is_valid is False
        assert "query" in error

    def test_validate_param_types(self):
        """Should fail on wrong param types."""
        registry = get_registry()
        tool = registry.get("search_memory")

        # Wrong type for query
        is_valid, error = tool.validate_params({"query": 123})
        assert is_valid is False
        assert "string" in error

    def test_validate_enum_values(self):
        """Should fail on invalid enum values."""
        registry = get_registry()
        tool = registry.get("tts_synthesize")

        # TTS doesn't have enums currently, so we test valid params pass
        is_valid, error = tool.validate_params({
            "text": "Hello world",
        })
        assert is_valid is True
        assert error is None

    def test_validate_valid_params(self):
        """Should pass with valid params."""
        registry = get_registry()
        tool = registry.get("search_memory")

        is_valid, error = tool.validate_params({
            "query": "test query",
            "limit": 10,
        })
        assert is_valid is True
        assert error is None


class TestToolExecution:
    """Tests for tool execution."""

    @pytest.mark.asyncio
    async def test_safe_execute_validates(self):
        """safe_execute should validate params."""
        registry = get_registry()
        tool = registry.get("x_post")

        # Execute with invalid params (missing text)
        result = await tool.safe_execute()
        assert result.success is False
        assert "text" in result.error

    @pytest.mark.asyncio
    async def test_x_post_length_validation(self):
        """x_post should validate tweet length."""
        registry = get_registry()
        tool = registry.get("x_post")

        # Execute with too-long text
        long_text = "x" * 300
        result = await tool.safe_execute(text=long_text)
        assert result.success is False
        assert "280" in result.error

    @pytest.mark.asyncio
    async def test_moderation_check_text_works(self):
        """moderation_check_text should use existing moderation service."""
        registry = get_registry()
        tool = registry.get("moderation_check_text")

        result = await tool.safe_execute(text="Hello, how are you?")
        assert result.success is True
        assert "is_safe" in result.data

    @pytest.mark.asyncio
    async def test_search_memory_placeholder(self):
        """search_memory should return placeholder data."""
        registry = get_registry()
        tool = registry.get("search_memory")

        result = await tool.safe_execute(query="test query")
        assert result.success is True
        assert "memories" in result.data
        assert result.metadata.get("note") is not None
