"""Ollama client integration for Local AI Sidekick."""
import json
import urllib.error
import urllib.request
from typing import Dict, List


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", timeout_seconds: int = 180):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def check_health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def is_model_available(self, model_name: str) -> bool:
        models = self.list_models()
        # Direct match or match without tag
        for m in models:
            if m == model_name or m.split(":")[0] == model_name.split(":")[0]:
                return True
        return False

    def chat_complete(self, model: str, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8") if e.fp else str(e)
            raise RuntimeError(f"Ollama API HTTP {e.code}: {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Failed to communicate with Ollama: {str(e)}")
