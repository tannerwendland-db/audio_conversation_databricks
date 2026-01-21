#!/usr/bin/env python3
"""
Search for tables and their lineage relationships in Databricks Unity Catalog.

This script helps discover how data assets are connected across the organization
by searching for tables and exploring their lineage graphs.

Usage:
    python search_lineage.py <search_pattern> [--catalog CATALOG] [--depth N]

Examples:
    python search_lineage.py sales
    python search_lineage.py orders --catalog main
    python search_lineage.py customer --catalog main --depth 2
"""

import argparse
import json
import subprocess
import sys
from collections import deque


def run_databricks_api(endpoint: str, method: str = "get") -> dict | None:
    """Run a Databricks API call using the CLI."""
    cmd = ["databricks", "api", method, endpoint]

    try:
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
        # Silently handle errors for search
        return None
    except json.JSONDecodeError:
        return None


def run_sql_query(query: str) -> list[dict] | None:
    """Run a SQL query using Databricks SQL execution API."""
    # Use statement execution API
    cmd = ["databricks", "sql", "query", query]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError:
        return None
    except json.JSONDecodeError:
        return None


def search_tables(pattern: str, catalog: str | None = None) -> list[str]:
    """Search for tables matching a pattern using information_schema."""
    tables = []

    # Search in information_schema
    if catalog:
        query = f"""
        SELECT table_catalog, table_schema, table_name
        FROM {catalog}.information_schema.tables
        WHERE LOWER(table_name) LIKE '%{pattern.lower()}%'
        LIMIT 50
        """
    else:
        # Search across catalogs - try system.information_schema
        query = f"""
        SELECT table_catalog, table_schema, table_name
        FROM system.information_schema.tables
        WHERE LOWER(table_name) LIKE '%{pattern.lower()}%'
        LIMIT 50
        """

    result = run_sql_query(query)
    if result:
        for row in result:
            cat = row.get("table_catalog", row.get("TABLE_CATALOG", ""))
            schema = row.get("table_schema", row.get("TABLE_SCHEMA", ""))
            table = row.get("table_name", row.get("TABLE_NAME", ""))
            if cat and schema and table:
                tables.append(f"{cat}.{schema}.{table}")

    return tables


def get_table_lineage(table_name: str) -> dict | None:
    """Get lineage information for a table."""
    endpoint = f"/api/2.0/lineage-tracking/table-lineage?table_name={table_name}&include_entity_lineage=true"
    return run_databricks_api(endpoint)


def extract_table_names_from_lineage(lineage_data: dict) -> tuple[list[str], list[str]]:
    """Extract table names from lineage response."""
    upstreams = []
    downstreams = []

    for item in lineage_data.get("upstreams", []):
        if "tableInfo" in item:
            info = item["tableInfo"]
            table = f"{info.get('catalog_name', '')}.{info.get('schema_name', '')}.{info.get('name', '')}"
            if table != "..":
                upstreams.append(table)

    for item in lineage_data.get("downstreams", []):
        if "tableInfo" in item:
            info = item["tableInfo"]
            table = f"{info.get('catalog_name', '')}.{info.get('schema_name', '')}.{info.get('name', '')}"
            if table != "..":
                downstreams.append(table)

    return upstreams, downstreams


def explore_lineage_graph(start_table: str, max_depth: int = 2) -> dict:
    """Explore lineage graph starting from a table up to max_depth levels."""
    graph = {
        "root": start_table,
        "nodes": {start_table: {"depth": 0, "upstreams": [], "downstreams": []}},
        "explored": set([start_table]),
    }

    # BFS to explore lineage
    queue = deque([(start_table, 0)])

    while queue:
        current_table, depth = queue.popleft()

        if depth >= max_depth:
            continue

        lineage = get_table_lineage(current_table)
        if lineage is None:
            continue

        upstreams, downstreams = extract_table_names_from_lineage(lineage)

        graph["nodes"][current_table]["upstreams"] = upstreams
        graph["nodes"][current_table]["downstreams"] = downstreams

        # Add newly discovered tables to explore
        for table in upstreams + downstreams:
            if table not in graph["explored"]:
                graph["explored"].add(table)
                graph["nodes"][table] = {"depth": depth + 1, "upstreams": [], "downstreams": []}
                queue.append((table, depth + 1))

    return graph


def print_lineage_graph(graph: dict) -> None:
    """Print a visual representation of the lineage graph."""
    root = graph["root"]
    nodes = graph["nodes"]

    print(f"\nLineage Graph for: {root}")
    print("=" * 70)

    # Print upstream tree
    print("\n[UPSTREAM - Data Sources]")
    print_tree(root, nodes, "upstream", set())

    # Print downstream tree
    print("\n[DOWNSTREAM - Data Consumers]")
    print_tree(root, nodes, "downstream", set())


def print_tree(table: str, nodes: dict, direction: str, visited: set, indent: int = 0) -> None:
    """Recursively print a tree structure."""
    if table in visited:
        return
    visited.add(table)

    prefix = "  " * indent
    arrow = "<-" if direction == "upstream" else "->"

    if indent == 0:
        print(f"  {table}")

    node = nodes.get(table, {})
    children = node.get(f"{direction}s", [])

    for child in children:
        print(f"  {prefix}  {arrow} {child}")
        print_tree(child, nodes, direction, visited, indent + 1)


def main():
    parser = argparse.ArgumentParser(
        description="Search for tables and explore their lineage relationships"
    )
    parser.add_argument(
        "pattern",
        help="Search pattern for table names",
    )
    parser.add_argument(
        "--catalog", "-c",
        help="Limit search to a specific catalog",
    )
    parser.add_argument(
        "--depth", "-d",
        type=int,
        default=1,
        help="How many levels of lineage to explore (default: 1)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON",
    )

    args = parser.parse_args()

    print(f"Searching for tables matching '{args.pattern}'...")
    tables = search_tables(args.pattern, args.catalog)

    if not tables:
        print(f"No tables found matching '{args.pattern}'")
        print("\nNote: Direct table search may require SQL warehouse access.")
        print("You can also specify a known table directly with get_table_lineage.py")
        sys.exit(0)

    print(f"Found {len(tables)} table(s):\n")

    results = []
    for table in tables:
        print(f"  - {table}")
        if args.depth > 0:
            graph = explore_lineage_graph(table, args.depth)
            results.append(graph)

    if args.json:
        print(json.dumps(results, indent=2, default=list))
    elif args.depth > 0 and results:
        for graph in results:
            print_lineage_graph(graph)


if __name__ == "__main__":
    main()
