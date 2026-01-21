#!/usr/bin/env python3
"""
List Databricks workspace contents with optional recursion.

Usage:
    python list_workspace.py /path/to/directory [--recursive] [--max-depth N]

Examples:
    python list_workspace.py /Users/user@company.com
    python list_workspace.py /Shared --recursive
    python list_workspace.py /Repos --recursive --max-depth 3
"""

import argparse
import json
import subprocess
import sys


def run_databricks_command(args: list[str]) -> dict | list | None:
    """Run a databricks CLI command and return parsed JSON output."""
    try:
        result = subprocess.run(
            ["databricks"] + args + ["--output", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error running databricks command: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}", file=sys.stderr)
        return None


def list_workspace(path: str) -> list[dict]:
    """List contents of a workspace path."""
    result = run_databricks_command(["workspace", "list", path])
    if result is None:
        return []
    # Handle both list and dict responses
    if isinstance(result, dict) and "objects" in result:
        return result["objects"]
    if isinstance(result, list):
        return result
    return []


def format_object(obj: dict, indent: int = 0) -> str:
    """Format a workspace object for display."""
    prefix = "  " * indent
    obj_type = obj.get("object_type", "UNKNOWN")
    path = obj.get("path", "")
    name = path.split("/")[-1] if path else ""

    type_indicator = {
        "DIRECTORY": "[DIR]",
        "NOTEBOOK": "[NB] ",
        "FILE": "[FILE]",
        "REPO": "[REPO]",
        "LIBRARY": "[LIB]",
    }.get(obj_type, "[???]")

    language = obj.get("language", "")
    lang_suffix = f" ({language.lower()})" if language else ""

    return f"{prefix}{type_indicator} {name}{lang_suffix}"


def list_recursive(path: str, max_depth: int, current_depth: int = 0) -> None:
    """Recursively list workspace contents."""
    objects = list_workspace(path)

    for obj in objects:
        print(format_object(obj, current_depth))

        if obj.get("object_type") == "DIRECTORY" and current_depth < max_depth:
            list_recursive(obj["path"], max_depth, current_depth + 1)


def main():
    parser = argparse.ArgumentParser(
        description="List Databricks workspace contents"
    )
    parser.add_argument(
        "path",
        help="Workspace path to list (e.g., /Users/user@company.com)",
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="List directories recursively",
    )
    parser.add_argument(
        "--max-depth", "-d",
        type=int,
        default=3,
        help="Maximum depth for recursive listing (default: 3)",
    )

    args = parser.parse_args()

    if args.recursive:
        print(f"Listing {args.path} (recursive, max depth: {args.max_depth})")
        print("-" * 50)
        list_recursive(args.path, args.max_depth)
    else:
        objects = list_workspace(args.path)
        if not objects:
            print(f"No objects found at {args.path} or path does not exist")
            return

        print(f"Contents of {args.path}:")
        print("-" * 50)
        for obj in objects:
            print(format_object(obj))


if __name__ == "__main__":
    main()
