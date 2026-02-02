"""
Jeffrey AIstein - Tool Registry

Central registry for all tools available to AIstein.
"""

from typing import Optional

import structlog

from services.tools.base import BaseTool, ToolCategory, ToolSchema

logger = structlog.get_logger()


class ToolRegistry:
    """
    Registry for managing available tools.

    Singleton pattern - use get_registry() to access.
    """

    _instance: Optional["ToolRegistry"] = None

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._schemas: dict[str, ToolSchema] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool with the registry.

        Args:
            tool: The tool instance to register
        """
        schema = tool.schema
        if schema.name in self._tools:
            logger.warning(
                "tool_already_registered",
                tool=schema.name,
                action="overwriting",
            )

        self._tools[schema.name] = tool
        self._schemas[schema.name] = schema
        logger.info("tool_registered", tool=schema.name, category=schema.category)

    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            name: The tool name

        Returns:
            The tool instance or None if not found
        """
        return self._tools.get(name)

    def get_schema(self, name: str) -> Optional[ToolSchema]:
        """
        Get a tool schema by name.

        Args:
            name: The tool name

        Returns:
            The tool schema or None if not found
        """
        return self._schemas.get(name)

    def list_tools(self, category: Optional[ToolCategory] = None) -> list[str]:
        """
        List all registered tool names.

        Args:
            category: Optional category filter

        Returns:
            List of tool names
        """
        if category is None:
            return list(self._tools.keys())

        return [
            name for name, schema in self._schemas.items()
            if schema.category == category
        ]

    def get_all_schemas(self, category: Optional[ToolCategory] = None) -> list[ToolSchema]:
        """
        Get all tool schemas.

        Args:
            category: Optional category filter

        Returns:
            List of tool schemas
        """
        if category is None:
            return list(self._schemas.values())

        return [
            schema for schema in self._schemas.values()
            if schema.category == category
        ]

    def get_anthropic_tools(self, category: Optional[ToolCategory] = None) -> list[dict]:
        """
        Get all tool schemas in Anthropic format.

        Args:
            category: Optional category filter

        Returns:
            List of tool definitions for Anthropic API
        """
        schemas = self.get_all_schemas(category)
        return [schema.to_anthropic_tool() for schema in schemas]

    def clear(self) -> None:
        """Clear all registered tools (for testing)."""
        self._tools.clear()
        self._schemas.clear()
        logger.info("tool_registry_cleared")


# Convenience function
def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return ToolRegistry.get_instance()


# Decorator for registering tools
def register_tool(cls):
    """
    Decorator to automatically register a tool class.

    Usage:
        @register_tool
        class MyTool(BaseTool):
            ...
    """
    instance = cls()
    get_registry().register(instance)
    return cls
