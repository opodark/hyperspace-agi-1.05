# SPDX-License-Identifier: Apache-2.0
"""Create, validate and publish one-file tools for Open WebUI.

Usage: python scripts/webui_tool.py new nome_tool
       python scripts/webui_tool.py check
       python scripts/webui_tool.py publish
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from shared.webui_tool_registry import NAME_RE, load_tools  # noqa: E402


PLUGIN_DIR = REPO / "shared" / "webui_custom_tools"
PLACEHOLDER = "# TODO: implementare il tool prima di pubblicarlo"


def create(name):
    if not NAME_RE.fullmatch(name):
        raise ValueError("Usa 2-64 caratteri: minuscole, numeri e underscore; inizia con una lettera")
    path = PLUGIN_DIR / f"{name}.py"
    source = f'''# SPDX-License-Identifier: Apache-2.0
from shared.webui_tool_registry import tool


@tool
def {name}(testo: str) -> dict:
    """Descrivi qui in modo chiaro cosa fa questo tool."""
    {PLACEHOLDER}
    raise NotImplementedError("Completa il tool prima di pubblicarlo")
'''
    with path.open("x", encoding="utf-8") as stream:
        stream.write(source)
    return path


def check():
    pending = [p.name for p in PLUGIN_DIR.glob("*.py")
               if p.name != "__init__.py" and PLACEHOLDER in p.read_text(encoding="utf-8")]
    if pending:
        raise ValueError("Tool da completare: " + ", ".join(pending))
    tools = load_tools()
    for item in tools.values():
        json.dumps({"properties": item.properties, "required": item.required})
    return sorted(tools)


def publish():
    names = check()
    subprocess.run(["docker", "compose", "up", "-d", "--build", "--no-deps", "control-plane"],
                   cwd=REPO, check=True)
    # Open WebUI caches the OpenAPI spec; restart to discover new operations.
    subprocess.run(["docker", "compose", "restart", "open-webui"], cwd=REPO, check=True)
    return names


def main():
    parser = argparse.ArgumentParser(description="Crea e pubblica tool Open WebUI da un file Python")
    parser.add_argument("action", choices=("new", "check", "publish"))
    parser.add_argument("name", nargs="?")
    args = parser.parse_args()
    try:
        if args.action == "new":
            if not args.name:
                parser.error("new richiede il nome del tool")
            print(f"Creato {create(args.name)}. Completa la funzione, poi esegui: python scripts/webui_tool.py publish")
        elif args.name:
            parser.error("il nome è ammesso solo con new")
        elif args.action == "check":
            print("Tool pronti:", ", ".join(check()) or "nessun tool personalizzato")
        else:
            print("Pubblicati:", ", ".join(publish()) or "solo i tool integrati")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Errore: {exc}\n")


if __name__ == "__main__":
    main()
