import json
import os
import time
import logging


class LLMError(Exception):
    """Raised on irrecoverable LLM evaluation failures."""

    pass


class LLM:
    def __init__(self, mode="stub", model="gpt-4o-mini", local_base_url=None):
        self.mode = mode
        self.model = model
        self.logger = logging.getLogger("Devbot.LLM")

        if self.mode != "stub":
            # Deferred import for lightweight startup when stubbed
            from openai import OpenAI

            if self.mode == "ollama":
                local_base_url = "http://localhost:11434/v1"
            self.client = OpenAI(
                base_url=local_base_url,
                api_key=os.environ.get("OPENAI_API_KEY", "stub-key"),
            )

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "propose_action",
                    "description": "Root-cause the anomaly and propose a safe remediation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tool": {
                                "type": "string",
                                "enum": [
                                    "restart_service",
                                    "shell",
                                    "git",
                                    "noop",
                                    "write_file",
                                    "read_file",
                                    "patch",
                                    "analyze",
                                    "scan",
                                    "test",
                                ],
                            },
                            "risk": {
                                "type": "integer",
                                "description": "Estimated risk level 0-3",
                            },
                            "args": {
                                "type": "object",
                                "description": "Arguments strictly required for the selected tool",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Root-cause analysis and why this tool was chosen",
                            },
                        },
                        "required": ["tool", "risk", "args", "reasoning"],
                    },
                },
            }
        ]

    def sanitize_prompt(self, prompt: str) -> str:
        """Heuristic defense against prompt injection."""
        # 1. Cap length to prevent context exhaustion attacks
        max_len = 16000
        if len(prompt) > max_len:
            self.logger.warning(
                f"Prompt truncated from {len(prompt)} to {max_len} chars."
            )
            prompt = prompt[:max_len] + "\n...[TRUNCATED]"

        # 2. Prevent role-impersonation overrides
        forbidden = ["Ignore previous instructions", "System override:", "You are now"]
        for phrase in forbidden:
            if phrase.lower() in prompt.lower():
                self.logger.warning(f"Injection syntax detected: '{phrase}'")
                prompt = prompt.replace(phrase, "[REDACTED]")

        return prompt

    def generate(self, prompt, max_tokens=512, retries=3):
        """Interact with the LLM using exponential backoff and schema validation."""
        if self.mode == "stub":
            return {"tool": "noop", "risk": 0, "args": {}, "reasoning": "Fallback stub"}

        clean_prompt = self.sanitize_prompt(prompt)

        backoff = 1.0
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a deterministic, bounded DevOps autonomous agent. "
                            "You strictly output JSON calling the `propose_action` function. "
                            "Do not apologize, explain, or output markdown outside the function structure.",
                        },
                        {"role": "user", "content": clean_prompt},
                    ],
                    tools=self.tools,
                    tool_choice={
                        "type": "function",
                        "function": {"name": "propose_action"},
                    },
                    max_tokens=max_tokens,
                    temperature=0.0,
                )

                raw_args = response.choices[0].message.tool_calls[0].function.arguments
                parsed = json.loads(raw_args)

                # Basic schema validation
                required_keys = {"tool", "risk", "args", "reasoning"}
                if not required_keys.issubset(parsed.keys()):
                    raise ValueError(
                        f"Missing required schema keys: {required_keys - parsed.keys()}"
                    )

                return parsed

            except json.JSONDecodeError as e:
                self.logger.error(
                    f"LLM returned invalid JSON (attempt {attempt+1}/{retries}): {e}"
                )
            except Exception as e:
                self.logger.error(
                    f"LLM API failure (attempt {attempt+1}/{retries}): {e}"
                )

            # Backoff before retry
            if attempt < retries - 1:
                time.sleep(backoff)
                backoff *= 2.0

        return {
            "tool": "noop",
            "risk": 0,
            "args": {},
            "reasoning": "LLM validation failed after retries",
        }
