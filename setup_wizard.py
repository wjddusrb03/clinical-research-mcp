"""Interactive setup wizard for clinical-research-mcp.

Configures Claude Desktop to use this MCP server.
No API keys are needed -- all data sources are free and public.
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path


def get_config_path() -> Path:
    """Auto-detect Claude Desktop config path for the current OS."""
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        # Linux / other
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        if xdg:
            return Path(xdg) / "Claude" / "claude_desktop_config.json"
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def backup_config(config_path: Path) -> Path | None:
    """Backup existing config file. Returns backup path or None."""
    if config_path.exists():
        backup_path = config_path.with_suffix(".json.bak")
        shutil.copy2(config_path, backup_path)
        return backup_path
    return None


def main():
    print("=" * 60)
    print("  clinical-research-mcp -- Setup Wizard")
    print("=" * 60)
    print()
    print("[INFO] This wizard configures Claude Desktop to use")
    print("       the clinical-research-mcp server.")
    print()
    print("[INFO] No API keys are needed.")
    print("       All data sources (PubMed, ClinicalTrials.gov,")
    print("       Wikipedia, arXiv) are free and public.")
    print()

    # Detect config path
    config_path = get_config_path()
    print(f"[INFO] Detected Claude Desktop config path:")
    print(f"       {config_path}")
    print()

    # Confirm with user
    answer = input("Proceed with setup? (y/n): ").strip().lower()
    if answer not in ("y", "yes"):
        print("[INFO] Setup cancelled.")
        sys.exit(0)

    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing config
    backup = backup_config(config_path)
    if backup:
        print(f"[INFO] Existing config backed up to: {backup}")

    # Load or create config
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError):
            print("[WARN] Could not parse existing config. Creating new one.")
            config = {}
    else:
        config = {}

    # Determine server.py path
    server_py = str(Path(__file__).resolve().parent / "server.py")

    # Add MCP server entry
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"]["clinical-research"] = {
        "command": "python",
        "args": [server_py],
    }

    # Write config
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print()
    print("[OK] Claude Desktop config updated successfully.")
    print()
    print("-" * 60)
    print("  Setup complete! Restart Claude Desktop to activate.")
    print("-" * 60)
    print()
    print("[INFO] Example prompts you can try:")
    print()
    print('  - "Search PubMed for recent CGRP migraine studies"')
    print('  - "Find recruiting clinical trials for Alzheimer\'s"')
    print('  - "Explain what CGRP is"')
    print('  - "Find arXiv papers on single-cell RNA sequencing"')
    print()


if __name__ == "__main__":
    main()
