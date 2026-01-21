#!/usr/bin/env python3
"""
Retrieve table lineage from Databricks Unity Catalog.

Usage:
    python get_table_lineage.py <catalog>.<schema>.<table> [--direction upstream|downstream|both]

Examples:
    python get_table_lineage.py main.sales.orders
    python get_table_lineage.py main.sales.orders --direction upstream
    python get_table_lineage.py main.sales.orders --direction downstream
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


def get_table_lineage(table_name: str, include_entity_lineage: bool = True) -> dict | None:
    """Get lineage information for a table."""
    endpoint = f"/api/2.0/lineage-tracking/table-lineage?table_name={table_name}&include_entity_lineage={str(include_entity_lineage).lower()}"
    return run_databricks_api(endpoint)


def format_entity(entity: dict) -> list[str]:
    """Format a lineage entity for display. Returns a list of formatted strings."""
    lines = []

    # Table info (singular) - the main related table
    if "tableInfo" in entity:
        info = entity["tableInfo"]
        table_name = f"{info.get('catalog_name', '')}.{info.get('schema_name', '')}.{info.get('name', '')}"
        lines.append(f"[TABLE] {table_name}")

    # Notebook infos (plural array)
    for info in entity.get("notebookInfos", []):
        notebook_id = info.get("notebook_id", "unknown")
        workspace_id = info.get("workspace_id", "")
        path = info.get("notebook_path", "")
        if path:
            lines.append(f"[NOTEBOOK] {path} (id: {notebook_id})")
        else:
            lines.append(f"[NOTEBOOK] workspace:{workspace_id} id:{notebook_id}")

    # Job infos (plural array)
    for info in entity.get("jobInfos", []):
        job_id = info.get("job_id", "unknown")
        job_name = info.get("job_name", "")
        workspace_id = info.get("workspace_id", "")
        if job_name:
            lines.append(f"[JOB] {job_name} (id: {job_id})")
        else:
            lines.append(f"[JOB] workspace:{workspace_id} id:{job_id}")

    # Pipeline infos (plural array)
    for info in entity.get("pipelineInfos", []):
        pipeline_id = info.get("pipeline_id", "unknown")
        pipeline_name = info.get("pipeline_name", "")
        workspace_id = info.get("workspace_id", "")
        if pipeline_name:
            lines.append(f"[PIPELINE] {pipeline_name} (id: {pipeline_id})")
        else:
            lines.append(f"[PIPELINE] workspace:{workspace_id} id:{pipeline_id}")

    # Dashboard infos (plural array) - handles both dashboardInfos and dashboardV3Infos
    for info in entity.get("dashboardInfos", []) + entity.get("dashboardV3Infos", []):
        dashboard_id = info.get("dashboard_id", "unknown")
        workspace_id = info.get("workspace_id", "")
        lines.append(f"[DASHBOARD] workspace:{workspace_id} id:{dashboard_id}")

    # Query infos (plural array)
    for info in entity.get("queryInfos", []):
        query_id = info.get("query_id", "unknown")
        workspace_id = info.get("workspace_id", "")
        lines.append(f"[QUERY] workspace:{workspace_id} id:{query_id}")

    # If nothing was parsed, show raw JSON
    if not lines:
        lines.append(f"[UNKNOWN] {json.dumps(entity)}")

    return lines


def print_lineage(lineage_data: dict, direction: str, table_name: str) -> None:
    """Print formatted lineage information."""
    print(f"\nLineage for: {table_name}")
    print("=" * 60)

    # Upstream lineage (data sources)
    if direction in ("upstream", "both"):
        upstreams = lineage_data.get("upstreams", [])
        print(f"\nUpstream (data sources): {len(upstreams)} connection(s)")
        print("-" * 40)
        if upstreams:
            for item in upstreams:
                for line in format_entity(item):
                    print(f"  {line}")
                print()  # Blank line between entries
        else:
            print("  No upstream dependencies found")

    # Downstream lineage (data consumers)
    if direction in ("downstream", "both"):
        downstreams = lineage_data.get("downstreams", [])
        print(f"\nDownstream (consumers): {len(downstreams)} connection(s)")
        print("-" * 40)
        if downstreams:
            for item in downstreams:
                for line in format_entity(item):
                    print(f"  {line}")
                print()  # Blank line between entries
        else:
            print("  No downstream dependencies found")


def main():
    parser = argparse.ArgumentParser(
        description="Retrieve table lineage from Databricks Unity Catalog"
    )
    parser.add_argument(
        "table_name",
        help="Fully qualified table name (catalog.schema.table)",
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

    lineage = get_table_lineage(args.table_name)

    if lineage is None:
        print(f"Failed to retrieve lineage for {args.table_name}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(lineage, indent=2))
    else:
        print_lineage(lineage, args.direction, args.table_name)


if __name__ == "__main__":
    main()
