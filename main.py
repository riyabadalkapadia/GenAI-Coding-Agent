# main.py
# GenAI Coding Agent — package layout (agent/*) + Windows-safe printing

import os
import sys
import argparse
import traceback
from typing import Optional

# Make stdout/stderr UTF-8 friendly on Windows; never crash on emojis/box chars
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

def safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        try:
            print(text.encode("ascii", "ignore").decode("ascii"))
        except Exception:
            print("")

# Ensure project root is on sys.path (covers running from VS Code or elsewhere)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# ---- Imports for your package layout (agent/...) ----
from agent.graph import agent          # expects agent/graph.py to expose `agent`
from agent.tools import init_project_root

# Optional .env loading
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

BANNER = r"""
============================================================
                 GENAI CODING AGENT (CLI)
============================================================
"""

def print_banner() -> None:
    safe_print(BANNER)

def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="GenAI Coding Agent",
        description=(
            "Generate or refactor code using an LLM agent. "
            "Supply a prompt with -p/--prompt or run interactively."
        ),
    )
    parser.add_argument(
        "-p", "--prompt",
        dest="user_prompt",
        type=str,
        default=None,
        help="Project/task description for the agent (quoted)."
    )
    parser.add_argument(
        "-r", "--recursion-limit",
        dest="recursion_limit",
        type=int,
        default=25,
        help="Max agent recursion/step limit (default: 25)."
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Hide the startup banner."
    )
    parser.add_argument(
        "--show-traceback",
        action="store_true",
        help="On error, show full Python traceback."
    )
    return parser.parse_args(argv)

def ensure_env_loaded() -> None:
    if load_dotenv:
        load_dotenv()
    missing = []
    if not os.getenv("GROQ_API_KEY"):
        missing.append("GROQ_API_KEY")
    if missing:
        safe_print("⚠️  Warning: Missing environment variable(s): " + ", ".join(missing))
        safe_print("    Create a .env file or export them in your shell.")

def prompt_interactively() -> str:
    safe_print("")
    safe_print("No prompt provided. Please describe what you want the agent to build/refactor:")
    safe_print("(Example: Build a modern todo app with HTML/CSS/JS using classes and localStorage.)")
    safe_print("")
    try:
        return input("> ").strip()
    except UnicodeDecodeError:
        return input("> ").encode("ascii", "ignore").decode("ascii").strip()

def main(argv: Optional[list] = None) -> None:
    args = parse_args(argv)

    if not args.no_banner:
        print_banner()

    ensure_env_loaded()

    # Prepare project output dirs etc.
    try:
        init_project_root()
    except Exception as e:
        safe_print("⚠️  Could not initialize project root via tools.init_project_root().")
        safe_print(f"    Details: {e}")

    user_prompt = args.user_prompt or prompt_interactively()
    if not user_prompt:
        safe_print("❌ ERROR: Empty prompt provided. Exiting.")
        sys.exit(2)

    safe_print("")
    safe_print("🚀 Running agent with the following parameters:")
    safe_print(f"   • Recursion limit: {args.recursion_limit}")
    safe_print(f"   • Prompt: {user_prompt}")
    safe_print("")

    try:
        result = agent.invoke(
            {"user_prompt": user_prompt},
            {"recursion_limit": int(args.recursion_limit)},
        )

        safe_print("✅ Done.")
        if result is not None:
            safe_print("—— Agent result ————————————————————————————————")
            try:
                if isinstance(result, str):
                    safe_print(result)
                elif hasattr(result, "content"):
                    safe_print(str(result.content))
                elif isinstance(result, dict) and "content" in result:
                    safe_print(str(result["content"]))
                else:
                    safe_print(str(result))
            except Exception:
                safe_print(str(result))
            safe_print("—————————————————————————————————————————————")
        else:
            safe_print("ℹ️  Agent returned no content.")

    except KeyboardInterrupt:
        safe_print("\n⏹️  Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        safe_print("❌ ERROR OCCURRED")
        safe_print(f"Reason: {e}")
        if args.show_traceback:
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
