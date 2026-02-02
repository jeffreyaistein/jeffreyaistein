"""
Jeffrey AIstein - Tool Base Interface

Defines the base interface for tools that AIstein can invoke.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger()


class ToolCategory(str, Enum):
    """Categories of tools available to AIstein."""
    MEMORY = "memory"
    TOKEN = "token"
    MODERATION = "moderation"
    TTS = "tts"
    SOCIAL = "social"


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[list] = None
    items: Optional[dict] = None  # For array types
    properties: Optional[dict] = None  # For object types


@dataclass
class ToolSchema:
    """Schema definition for a tool."""
    name: str
    description: str
    category: ToolCategory
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_json_schema(self) -> dict:
        """Convert to JSON Schema format for LLM tool calling."""
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }

            if param.enum:
                prop["enum"] = param.enum

            if param.type == "array" and param.items:
                prop["items"] = param.items

            if param.type == "object" and param.properties:
                prop["properties"] = param.properties

            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    def to_anthropic_tool(self) -> dict:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.to_json_schema(),
        }


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for tools."""

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """Return the tool's schema."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given parameters."""
        pass

    def validate_params(self, params: dict) -> tuple[bool, Optional[str]]:
        """
        Validate parameters against the schema.

        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = self.schema

        # Check required parameters
        for param in schema.parameters:
            if param.required and param.name not in params:
                return False, f"Missing required parameter: {param.name}"

        # Check parameter types
        for param in schema.parameters:
            if param.name not in params:
                continue

            value = params[param.name]

            if param.type == "string" and not isinstance(value, str):
                return False, f"Parameter {param.name} must be a string"

            if param.type == "number" and not isinstance(value, (int, float)):
                return False, f"Parameter {param.name} must be a number"

            if param.type == "boolean" and not isinstance(value, bool):
                return False, f"Parameter {param.name} must be a boolean"

            if param.type == "array" and not isinstance(value, list):
                return False, f"Parameter {param.name} must be an array"

            if param.type == "object" and not isinstance(value, dict):
                return False, f"Parameter {param.name} must be an object"

            if param.enum and value not in param.enum:
                return False, f"Parameter {param.name} must be one of: {param.enum}"

        return True, None

    async def safe_execute(self, **kwargs) -> ToolResult:
        """Execute with validation and error handling."""
        # Validate parameters
        is_valid, error = self.validate_params(kwargs)
        if not is_valid:
            logger.warning(
                "tool_validation_failed",
                tool=self.schema.name,
                error=error,
            )
            return ToolResult(success=False, error=error)

        try:
            result = await self.execute(**kwargs)
            logger.info(
                "tool_executed",
                tool=self.schema.name,
                success=result.success,
            )
            return result
        except Exception as e:
            logger.error(
                "tool_execution_error",
                tool=self.schema.name,
                error=str(e),
            )
            return ToolResult(success=False, error=str(e))
