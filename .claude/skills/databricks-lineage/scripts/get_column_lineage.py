#!/usr/bin/env python3
"""
Retrieve column-level lineage from Databricks Unity Catalog.

Usage:
    python get_column_lineage.py <catalog>.<schema>.<table> <column_name> [--direction upstream|downstream|both]

Examples:
    python get_column_lineage.py main.sales.orders order_id
    python get_column_lineage.py main.sales.orders total_amount --direction upstream
"""

import argparse
import json
import subprocess
import sys


def run_databricks_api(endpoint: str, method: str = "get", data: dict | None = None) -> dict | None:
    """Run a Databricks API call using the CLI."""
    cmd = ["databricks", "api", method, endpoint]

    try:
        if data:
            result = subprocess.run(
                cmd + ["--json", json.dumps(data)],
                capture_output=True,
                text=True,
                check=True,
            )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error calling Databricks API: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}", file=sys.stderr)
        return None


def get_column_lineage(table_name: str, column_name: str) -> dict | None:
    """Get column-level lineage information."""
    endpoint = f"/api/2.0/lineage-tracking/column-lineage?table_name={table_name}&column_name={column_name}"
    return run_databricks_api(endpoint)


def format_column_ref(col_ref: dict) -> str:
    """Format a column reference for display."""
    table = col_ref.get("table_name", "unknown")
    column = col_ref.get("column_name", "unknown")
    return f"{table}.{column}"


def print_column_lineage(lineage_data: dict, table_name: str, column_name: str, direction: str) -> None:
    """Print formatted column lineage information."""
    print(f"\nColumn Lineage for: {table_name}.{column_name}")
    print("=" * 60)

    # Upstream lineage (source columns)
    if direction in ("upstream", "both"):
        upstreams = lineage_data.get("upstream_cols", [])
        print(f"\nUpstream (source columns): {len(upstreams)} found")
        print("-" * 40)
        if upstreams:
            for col in upstreams:
                print(f"  <- {format_column_ref(col)}")
        else:
            print("  No upstream columns found (may be a source column or use path-based reference)")

    # Downstream lineage (derived columns)
    if direction in ("downstream", "both"):
        downstreams = lineage_data.get("downstream_cols", [])
        print(f"\nDownstream (derived columns): {len(downstreams)} found")
        print("-" * 40)
        if downstreams:
            for col in downstreams:
                print(f"  -> {format_column_ref(col)}")
        else:
            print("  No downstream columns found")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve column-level lineage from Databricks Unity Catalog"
    )
    parser.add_argument(
        "table_name",
        help="Fully qualified table name (catalog.schema.table)",
    )
    parser.add_argument(
        "column_name",
        help="Column name to trace lineage for",
    )
    parser.add_argument(
        "--direction", "-d",
        choices=["upstream", "downstream", "both"],
        default="both",
        help="Lineage direction to show (default: both)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response",
    )

    args = parser.parse_args()

    # Validate table name format
    parts = args.table_name.split(".")
    if len(parts) != 3:
        print("Error: Table name must be fully qualified (catalog.schema.table)", file=sys.stderr)
        sys.exit(1)

    lineage = get_column_lineage(args.table_name, args.column_name)

    if lineage is None:
        print(f"Failed to retrieve column lineage for {args.table_name}.{args.column_name}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(lineage, indent=2))
    else:
        print_column_lineage(lineage, args.table_name, args.column_name, args.direction)


if __name__ == "__main__":
    main()
