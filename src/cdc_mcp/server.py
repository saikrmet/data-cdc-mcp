"""
MCP Server for data.cdc.gov — powered by FastMCP.

Tool flow for a typical question:
  cdc_search_datasets → cdc_get_dataset_schema → cdc_query_dataset
                                               ↗ (optional preview first)
                           cdc_get_sample_rows

Run:
  data-cdc-mcp                              # stdio — for local MCP clients (Claude Desktop, etc.)
  data-cdc-mcp serve                        # streamable-http — for production/Azure deployment
  data-cdc-mcp serve --host 127.0.0.1 --port 9000
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import FastMCP
from typing import Annotated

from cdc_mcp import client

load_dotenv()

MAX_ROWS = int(os.getenv("CDC_MAX_ROWS", "500"))
DEFAULT_ROWS = int(os.getenv("CDC_DEFAULT_ROWS", "50"))

mcp = FastMCP(
    name="data-cdc-gov",
    instructions=(
        "This server provides access to data.cdc.gov, the CDC's public health open data portal "
        "with ~10,000 datasets powered by the Socrata API. "
        "Typical workflow: (1) call cdc_search_datasets to find relevant dataset IDs, "
        "(2) call cdc_get_dataset_schema to learn the column field names and sample values, "
        "(3) optionally call cdc_get_sample_rows to preview actual data, "
        "(4) call cdc_query_dataset with specific columns and filters. "
        "Always use field names (not display names) in queries. Never use SELECT *."
    ),
)


# ---------------------------------------------------------------------------
# Tool 1: Dataset discovery
# ---------------------------------------------------------------------------

@mcp.tool
async def cdc_search_datasets(
    query: Annotated[
        str,
        "Search query using only semantically rich keywords like topics, diseases, etc. — treat this like a search engine. "
        "Use specific health topic words and population terms. "
        "Avoid generic words like 'data', 'rates', 'prevalence', 'estimates', 'trends'. "
    ],
    limit: Annotated[
        int,
        "Number of candidate datasets to return (1–10, default 5).",
    ] = 5,
) -> str:
    """Search data.cdc.gov for datasets relevant to a topic or question.

    Returns candidate datasets with their IDs, descriptions, column names/types,
    tags, and freshness. Use multi-word queries for best results.
    Call this first to identify which dataset to query.
    """
    limit = min(limit, 10)
    data = await client.catalog_search(query, limit)
    results = data.get("results", [])
    total = data.get("resultSetSize", 0)

    if not results:
        return f"No datasets found for '{query}'. Try broader or different keywords."

    datasets = []
    for r in results:
        resource = r.get("resource", {})
        classification = r.get("classification", {})
        col_descriptions = resource.get("columns_description") or []
        col_names = resource.get("columns_name", [])

        datasets.append({
            "id": resource.get("id"),
            "name": resource.get("name"),
            "description": (resource.get("description") or "")[:300],
            "category": classification.get("domain_category"),
            "tags": classification.get("domain_tags", []),
            "columns": [
                {
                    "name": n,
                    "field_name": f,
                    "type": t,
                    "description": d,
                }
                for n, f, t, d in zip(
                    col_names,
                    resource.get("columns_field_name", []),
                    resource.get("columns_datatype", []),
                    col_descriptions if col_descriptions else [""] * len(col_names),
                )
            ],
            "last_updated": resource.get("data_updated_at"),
            "page_views_total": resource.get("page_views", {}).get("total", 0),
            "permalink": r.get("permalink"),
        })

    return json.dumps({
        "query": query,
        "total_matching_datasets": total,
        "showing": len(datasets),
        "datasets": datasets,
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: Schema resolution
# ---------------------------------------------------------------------------

@mcp.tool
async def cdc_get_dataset_schema(
    dataset_id: Annotated[
        str,
        "8-character Socrata dataset identifier (e.g. 'ksfb-ug5d'). "
        "Obtained from cdc_search_datasets results.",
    ],
) -> str:
    """Get full column metadata for a specific CDC dataset.

    Returns each column's API field name (for use in SoQL queries), data type,
    description, sample values, and min/max range.
    Call this after cdc_search_datasets to understand the dataset structure
    before building a query.
    """
    meta = await client.dataset_metadata(dataset_id.strip())

    dataset_info = {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "description": meta.get("description"),
        "category": meta.get("category"),
        "tags": meta.get("tags", []),
        "update_frequency": (
            meta.get("metadata", {})
            .get("custom_fields", {})
            .get("Common Core", {})
            .get("Update Frequency")
        ),
        "row_count_estimate": _estimate_row_count(meta),
    }

    columns = []
    for col in meta.get("columns", []):
        cached = col.get("cachedContents", {})
        top_values = [
            entry.get("item") for entry in (cached.get("top") or [])[:5]
            if entry.get("item") is not None
        ]
        columns.append({
            "field_name": col.get("fieldName"),
            "display_name": col.get("name"),
            "type": col.get("dataTypeName"),
            "description": col.get("description"),
            "sample_values": top_values,
            "value_range": {
                "min": cached.get("smallest"),
                "max": cached.get("largest"),
            } if cached.get("smallest") is not None else None,
            "cardinality": cached.get("cardinality"),
            "non_null_count": cached.get("non_null"),
        })

    return json.dumps({
        "dataset": dataset_info,
        "columns": columns,
        "soql_endpoint": f"https://data.cdc.gov/resource/{dataset_id}.json",
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 3: Query execution
# ---------------------------------------------------------------------------

@mcp.tool
async def cdc_query_dataset(
    dataset_id: Annotated[str, "8-character Socrata dataset identifier."],
    select: Annotated[
        list[str],
        "Columns to return. Use exact fieldNames from cdc_get_dataset_schema — not display names. "
        "Supports SoQL expressions and aliases, e.g. 'sum(new_cases) AS total_cases'. "
        "Required — SELECT * is not allowed.",
    ],
    where: Annotated[
        str | None,
        "SoQL WHERE clause (omit the '$where=' prefix). "
        "Examples: \"state = 'NY'\", \"mmwr_year >= 2024\", \"date_extract_y(report_date) = 2024\". "
        "IMPORTANT: SoQL reserved words used as column names must be backtick-escaped to avoid 400 errors. "
        "Common reserved column names: `group`, `select`, `where`, `order`, `limit`, `offset`. "
        "Example: \"`group` = 'By Total'\" not \"group = 'By Total'\".",
    ] = None,
    group_by: Annotated[
        list[str] | None,
        "Columns to GROUP BY when using aggregate functions (count, sum, avg, min, max) in select.",
    ] = None,
    order_by: Annotated[
        str | None,
        "Sort expression, e.g. 'mmwr_week ASC' or 'total_cases DESC'.",
    ] = None,
    limit: Annotated[
        int,
        f"Rows to return per call (default {DEFAULT_ROWS}, max {MAX_ROWS}).",
    ] = DEFAULT_ROWS,
    offset: Annotated[
        int,
        "Row offset for pagination (0-indexed, default 0).",
    ] = 0,
    search: Annotated[
        str | None,
        "Full-text search term applied across all text fields. Stemmed, multi-term AND logic.",
    ] = None,
) -> str:
    """Execute a SoQL query against a CDC dataset and return paginated results.

    You must specify which columns to return (no SELECT *).
    Use field names from cdc_get_dataset_schema, not display names.
    Results are capped server-side to prevent context flooding.
    Check has_more and use offset for subsequent pages.
    """
    dataset_id = dataset_id.strip()
    limit = min(limit, MAX_ROWS)
    offset = max(offset, 0)

    if not select:
        return (
            "'select' is required. Specify column field names to return. "
            "Use cdc_get_dataset_schema to find valid field names."
        )

    # Validate plain column names (skip SoQL expressions containing functions/aliases)
    plain_columns = [
        s.strip() for s in select
        if not any(c in s for c in ["(", ")", " AS ", " as "])
    ]
    if plain_columns:
        meta = await client.dataset_metadata(dataset_id)
        valid_fields = {col["fieldName"] for col in meta.get("columns", [])}
        invalid = [c for c in plain_columns if c not in valid_fields]
        if invalid:
            return (
                f"Invalid column(s) in select: {invalid}. "
                f"Valid field names for this dataset: {sorted(valid_fields)}"
            )

    # Run count + data queries concurrently
    total_estimate, rows = await asyncio.gather(
        client.dataset_row_count(dataset_id, where=where, search=search),
        client.dataset_query(
            dataset_id=dataset_id,
            select=select,
            where=where,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
            offset=offset,
            search=search,
        ),
    )

    has_more = (offset + len(rows)) < total_estimate
    soql_parts = [f"SELECT {', '.join(select)}"]
    if where:
        soql_parts.append(f"WHERE {where}")
    if group_by:
        soql_parts.append(f"GROUP BY {', '.join(group_by)}")
    if order_by:
        soql_parts.append(f"ORDER BY {order_by}")
    soql_parts.append(f"LIMIT {limit} OFFSET {offset}")

    return json.dumps({
        "dataset_id": dataset_id,
        "query_executed": " ".join(soql_parts),
        "row_count": len(rows),
        "total_estimate": total_estimate,
        "has_more": has_more,
        "next_offset": offset + len(rows) if has_more else None,
        "columns_returned": list(rows[0].keys()) if rows else [],
        "rows": rows,
    }, indent=2)


# ---------------------------------------------------------------------------
# Tool 4: Sample rows
# ---------------------------------------------------------------------------

@mcp.tool
async def cdc_get_sample_rows(
    dataset_id: Annotated[str, "8-character Socrata dataset identifier."],
    limit: Annotated[
        int,
        "Number of sample rows to return (1–20, default 5).",
    ] = 5,
) -> str:
    """Preview a small number of raw rows from a CDC dataset.

    Useful for understanding the actual data shape, real column values, and how
    to construct WHERE filters before writing a full query.
    Call this when you need to see concrete data examples.
    """
    limit = min(limit, 20)
    rows = await client.dataset_query(dataset_id.strip(), limit=limit, offset=0)

    return json.dumps({
        "dataset_id": dataset_id,
        "sample_row_count": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "rows": rows,
    }, indent=2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_row_count(meta: dict) -> int | None:
    for col in meta.get("columns", []):
        non_null = col.get("cachedContents", {}).get("non_null")
        if non_null:
            try:
                return int(non_null)
            except (ValueError, TypeError):
                pass
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="CDC data.cdc.gov MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  data-cdc-mcp                          # stdio (local MCP clients)\n"
            "  data-cdc-mcp serve                    # streamable-http on 0.0.0.0:8000\n"
            "  data-cdc-mcp serve --port 9000        # custom port\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run as a streamable-http server (production/Azure)")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")

    args = parser.parse_args()

    if args.command == "serve":
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
