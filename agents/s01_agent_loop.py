#!/usr/bin/env python3
# Harness: the loop -- the model's first connection to the real world.
"""
s01_agent_loop.py - The Agent Loop

The entire secret of an AI coding agent in one pattern:

    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          (loop continues)

This is the core loop: feed tool results back to the model
until the model decides to stop. Production agents layer
policy, hooks, and lifecycle controls on top.

Supports both Anthropic and Gemini APIs via common.py adapter.
"""

import os
import subprocess

import os
import subprocess

from common import LLM, convert_tools_to_openai_format, MODEL

SYSTEM = f"""You are a coding agent at {os.getcwd()}.
IMPORTANT: You are on Windows! Use Windows commands only:
- Use 'dir' instead of 'ls'
- Use 'type' instead of 'cat'
- Use 'cd' without arguments to show directory
- Use 'del /s /q' instead of 'rm -rf'
- Use 'mkdir' without -p flag
- Use 'echo' without -n flag
Act, don't explain."""

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    }
]


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"

    # Translate Linux commands to Windows equivalents
    linux_to_windows = [
        ("ls -la", "dir"),
        ("ls -l", "dir"),
        ("ls -al", "dir /a"),
        ("ls -a", "dir /a"),
        (r"\bls\b", "dir"),
        ("pwd", "cd"),
        ("cat ", "type "),
        ("cat'", "type "),
        ("rm -rf ", "rmdir /s /q "),
        ("rm -r ", "rmdir /s /q "),
        ("rm ", "del "),
        ("mkdir -p ", "mkdir "),
        ("touch ", "type nul > "),
        ("echo -n ", "echo "),
        ("grep ", "findstr "),
        ("sed ", "powershell -c "),
        ("awk ", "powershell -c "),
        ("which ", "where "),
        ("head -n ", "powershell -c "),
        ("tail -n ", "powershell -c "),
        ("wc -l", "find /c /v"),
    ]

    cmd = command
    for linux, windows in linux_to_windows:
        import re

        if re.search(linux, cmd):
            cmd = re.sub(linux, windows, cmd)

    try:
        r = subprocess.run(
            cmd,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    import json

    tools = convert_tools_to_openai_format(TOOLS)
    while True:
        response = LLM.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=tools,
            max_tokens=8000,
        )
        if not LLM.is_tool_call(response):
            assistant_msg = LLM.format_assistant_message(response)
            messages.append(assistant_msg)
            return

        assistant_msg = LLM.format_assistant_message(response)
        messages.append(assistant_msg)

        # Debug: print the messages being sent
        # print(f"DEBUG: messages count = {len(messages)}")

        results = []
        for block in LLM.get_tool_calls(response):
            name = LLM.get_tool_name(block)
            args = LLM.get_tool_args(block)
            command = args.get("command", "")
            print(f"\033[33m$ {command}\033[0m")
            output = run_bash(command)
            print(output[:200] if output else "")
            results.append(LLM.format_tool_result(block, output))

        # Append tool results one at a time (proper format for Gemini)
        for result in results:
            messages.append(result)


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        print(history[-1]["content"])
        print()
