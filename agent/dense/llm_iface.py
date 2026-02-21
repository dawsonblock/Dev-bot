import json
import os

class LLM:
    def __init__(self, mode="stub", model="gpt-4o-mini", local_base_url=None):
        self.mode = mode
        self.model = model

        if self.mode != "stub":
            from openai import OpenAI
            if self.mode == "ollama":
                local_base_url = "http://localhost:11434/v1"
            self.client = OpenAI(
                base_url=local_base_url,
                api_key=os.environ.get("OPENAI_API_KEY", "stub-key")
            )

        self.tools = [{
            "type": "function",
            "function": {
                "name": "propose_action",
                "description": "Root-cause the anomaly and propose a safe remediation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string", "enum": ["restart_service", "shell", "git", "noop"]},
                        "risk": {"type": "integer", "description": "Estimated risk level 0-3"},
                        "args": {"type": "object", "description": "Arguments required for the selected tool"},
                        "reasoning": {"type": "string", "description": "Root-cause analysis and why this tool was chosen"}
                    },
                    "required": ["tool", "risk", "args", "reasoning"]
                }
            }
        }]

    def generate(self, prompt, max_tokens=256):
        if self.mode == "stub":
            return {"tool": "restart_service", "risk": 1, "args": {"name": "svc"}, "reasoning": "Fallback stub"}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a deterministic, bounded DevOps agent. Obey risk envelopes strictly."},
                    {"role": "user", "content": prompt}
                ],
                tools=self.tools,
                tool_choice={"type": "function", "function": {"name": "propose_action"}},
                max_tokens=max_tokens,
                temperature=0.0
            )
            raw_args = response.choices[0].message.tool_calls[0].function.arguments
            return json.loads(raw_args)
        except Exception as e:
            return {"tool": "noop", "risk": 0, "args": {}, "reasoning": f"LLM error: {str(e)}"}
