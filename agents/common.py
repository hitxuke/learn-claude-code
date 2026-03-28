#!/usr/bin/env python3
"""
common.py - LLM API Adapter Layer

Provides a unified interface for both Anthropic and Gemini (OpenAI-compatible) APIs.
Auto-detects which API to use based on available environment variables.

Usage:
    from common import LLM

    # Auto-detects API based on env vars
    response = LLM.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS,
        system=SYSTEM,
        max_tokens=8000
    )

    # Unified access patterns
    if LLM.is_tool_call(response):
        for block in LLM.get_tool_calls(response):
            name = LLM.get_tool_name(block)
            args = LLM.get_tool_args(block)
            output = handler(name, args)
            results.append(LLM.format_tool_result(block, output))
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv(override=True)


class APIConfig:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    MODEL_ID = os.getenv("MODEL_ID", "gemini-1.5-flash")
    BASE_URL = os.getenv("BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    @classmethod
    def use_gemini(cls) -> bool:
        return bool(cls.GEMINI_API_KEY) and not bool(cls.ANTHROPIC_API_KEY)

    @classmethod
    def use_anthropic(cls) -> bool:
        return bool(cls.ANTHROPIC_API_KEY)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


class AnthropicAdapter:
    def __init__(self):
        from anthropic import Anthropic

        base_url = os.getenv("ANTHROPIC_BASE_URL")
        self.client = Anthropic(base_url=base_url) if base_url else Anthropic()

    def create(
        self,
        model: str,
        messages: list,
        tools: list,
        system: str = None,
        max_tokens: int = 8000,
    ) -> Any:
        kwargs = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        return self.client.messages.create(**kwargs)

    @staticmethod
    def is_tool_call(response: Any) -> bool:
        return response.stop_reason == "tool_use"

    @staticmethod
    def get_tool_calls(response: Any) -> list:
        return [b for b in response.content if b.type == "tool_use"]

    @staticmethod
    def get_tool_name(block: Any) -> str:
        return block.name

    @staticmethod
    def get_tool_args(block: Any) -> dict:
        return block.input

    @staticmethod
    def get_tool_id(block: Any) -> str:
        return block.id

    @staticmethod
    def format_tool_result(block: Any, content: str) -> dict:
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": content,
        }

    @staticmethod
    def format_assistant_message(response: Any) -> dict:
        return {
            "role": "assistant",
            "content": response.content,
        }

    @staticmethod
    def get_response_text(response: Any) -> str:
        if hasattr(response, "content"):
            texts = []
            for block in response.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
            return "\n".join(texts)
        return ""


class GeminiAdapter:
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(self):
        from openai import OpenAI

        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        base_url = os.getenv("BASE_URL") or self.DEFAULT_BASE_URL
        print(f"[GeminiAdapter] Using base_url: {base_url}")
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.base_url = base_url

    def create(
        self,
        model: str,
        messages: list,
        tools: list,
        system: str = None,
        max_tokens: int = 8000,
    ) -> Any:
        if system:
            messages = [{"role": "system", "content": system}] + list(messages)
        # Only add models/ prefix for Google APIs
        if "generativelanguage.googleapis.com" in self.base_url:
            model = f"models/{model}" if not model.startswith("models/") else model
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )

    @staticmethod
    def is_tool_call(response: Any) -> bool:
        return response.choices[0].finish_reason == "tool_calls"

    @staticmethod
    def get_tool_calls(response: Any) -> list:
        msg = response.choices[0].message
        return msg.tool_calls or []

    @staticmethod
    def get_tool_name(tool_call: Any) -> str:
        return tool_call.function.name

    @staticmethod
    def get_tool_args(tool_call: Any) -> dict:
        return json.loads(tool_call.function.arguments)

    @staticmethod
    def get_tool_id(tool_call: Any) -> str:
        return tool_call.id

    @staticmethod
    def format_tool_result(tool_call: Any, content: str) -> dict:
        return {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": content,
            "name": tool_call.function.name
            if hasattr(tool_call, "function")
            else tool_call.get("function", {}).get("name", "unknown"),
        }

    @staticmethod
    def format_assistant_message(response: Any) -> dict:
        msg = response.choices[0].message
        tool_calls = msg.tool_calls if msg.tool_calls else []

        if tool_calls:
            return {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                            if isinstance(tc.function.arguments, str)
                            else json.dumps(tc.function.arguments),
                        },
                    }
                    for tc in tool_calls
                ],
            }
        else:
            return {
                "role": "assistant",
                "content": msg.content or "",
            }

    @staticmethod
    def get_response_text(response: Any) -> str:
        return response.choices[0].message.content or ""


class LLM:
    _adapter = None

    @classmethod
    def _get_adapter(cls):
        if cls._adapter is None:
            if APIConfig.use_gemini():
                print(f"[LLM] Using Gemini API")
                cls._adapter = GeminiAdapter()
            elif APIConfig.use_anthropic():
                print(f"[LLM] Using Anthropic API")
                cls._adapter = AnthropicAdapter()
            else:
                if APIConfig.GEMINI_API_KEY:
                    print(f"[LLM] Using Gemini API (fallback: GEMINI_API_KEY found)")
                    cls._adapter = GeminiAdapter()
                else:
                    raise ValueError(
                        "No API key found. Set GEMINI_API_KEY or ANTHROPIC_API_KEY"
                    )

        if cls._adapter is None:
            raise RuntimeError("Failed to initialize LLM adapter")
        return cls._adapter

    @classmethod
    def reset(cls):
        cls._adapter = None

    @classmethod
    def create(
        cls,
        model: str,
        messages: list,
        tools: list,
        system: str = None,
        max_tokens: int = 8000,
    ) -> Any:
        adapter = cls._get_adapter()
        return adapter.create(model, messages, tools, system, max_tokens)

    @classmethod
    def is_tool_call(cls, response: Any) -> bool:
        adapter = cls._get_adapter()
        return adapter.is_tool_call(response)

    @classmethod
    def get_tool_calls(cls, response: Any) -> list:
        adapter = cls._get_adapter()
        return adapter.get_tool_calls(response)

    @classmethod
    def get_tool_name(cls, block: Any) -> str:
        adapter = cls._get_adapter()
        return adapter.get_tool_name(block)

    @classmethod
    def get_tool_args(cls, block: Any) -> dict:
        adapter = cls._get_adapter()
        return adapter.get_tool_args(block)

    @classmethod
    def get_tool_id(cls, block: Any) -> str:
        adapter = cls._get_adapter()
        return adapter.get_tool_id(block)

    @classmethod
    def format_tool_result(cls, block: Any, content: str) -> dict:
        adapter = cls._get_adapter()
        return adapter.format_tool_result(block, content)

    @classmethod
    def format_assistant_message(cls, response: Any) -> dict:
        adapter = cls._get_adapter()
        return adapter.format_assistant_message(response)

    @classmethod
    def get_response_text(cls, response: Any) -> str:
        adapter = cls._get_adapter()
        return adapter.get_response_text(response)


def convert_tools_to_openai_format(tools: list) -> list:
    converted = []
    for tool in tools:
        if "input_schema" in tool:
            converted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["input_schema"],
                    },
                }
            )
        else:
            converted.append(tool)
    return converted


MODEL = APIConfig.MODEL_ID
