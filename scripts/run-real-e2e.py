#!/usr/bin/env python3
"""Run real Ollama E2E tests (dedicated real-runtime validation lane).

Usage:
    python scripts/run-real-e2e.py [--model qwen2.5:14b]
"""
import argparse
import json
import os
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path


def check_ollama(base_url: str, model_name: str) -> bool:
    url = f"{base_url.rstrip('/')}/api/tags"
    print(f"[*] Probing Ollama at {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sidekick-e2e/0.2.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            installed = [m.get("name", "") for m in data.get("models", [])]
            print(f"[+] Ollama is online. Installed models: {', '.join(installed) if installed else '(none)'}")
            matched = any(
                model_name == m or model_name == m.split(":")[0] or m.startswith(f"{model_name}:")
                for m in installed
            )
            if not matched:
                print(f"[!] Warning: Model '{model_name}' not found in installed models.")
                print(f"    Please run: ollama pull {model_name}")
                return False
            print(f"[+] Model '{model_name}' is ready.")
            return True
    except urllib.error.URLError as e:
        print(f"[x] Error: Cannot connect to Ollama at {url}: {e.reason}")
        print("    Please ensure Ollama is running (`ollama serve` or Ollama desktop app).")
        return False
    except Exception as e:
        print(f"[x] Unexpected error connecting to Ollama: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run real Ollama E2E test suite")
    parser.add_argument("--model", type=str, default="qwen2.5:14b", help="Model name to test against (default: qwen2.5:14b)")
    parser.add_argument("--ollama-url", type=str, default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--skip-check", action="store_true", help="Skip pre-flight Ollama health probe")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent.resolve()
    sys.path.insert(0, str(repo_root / "src"))

    if not args.skip_check:
        ready = check_ollama(args.ollama_url, args.model)
        if not ready:
            print("\n[!] Pre-flight check failed. Aborting real Ollama E2E run.")
            sys.exit(1)

    print(f"\n[*] Starting Real Ollama E2E Suite with model '{args.model}'...")
    os.environ["SIDEKICK_RUN_REAL_OLLAMA_E2E"] = "true"
    os.environ["SIDEKICK_MODEL"] = args.model
    os.environ["SIDEKICK_OLLAMA_BASE_URL"] = args.ollama_url

    loader = unittest.TestLoader()
    suite = loader.discover(str(repo_root / "tests"), pattern="test_phase2_e2e.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
