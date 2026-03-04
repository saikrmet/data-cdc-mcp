"""
Quick manual test for all 4 CDC MCP tools.

Edit the variables in each section below, then run:
    python test_tools.py
"""

import asyncio
import json
import sys

# Add src to path so we can import cdc_mcp without installing
sys.path.insert(0, "src")

from cdc_mcp import client

# ===========================================================================
# CONFIGURE YOUR TEST INPUTS HERE
# ===========================================================================

# Tool 1 — Search for datasets
SEARCH_QUERY = "adult obesity rates by state"
SEARCH_LIMIT = 5  # 1–10

# Tool 2 — Get schema for a specific dataset
# (paste a dataset ID from the search results above, or use this example)
SCHEMA_DATASET_ID = "ksfb-ug5d"

# Tool 3 — Query a dataset
QUERY_DATASET_ID = "ksfb-ug5d"
QUERY_SELECT = ["state", "year", "deaths"]   # column field names (not display names)
QUERY_WHERE = None                            # e.g. "state = 'NY'" or None
QUERY_ORDER_BY = "deaths DESC"               # e.g. "year ASC" or None
QUERY_LIMIT = 10

# Tool 4 — Preview raw rows
SAMPLE_DATASET_ID = "ksfb-ug5d"
SAMPLE_LIMIT = 5  # 1–20

# ===========================================================================


def header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def show(result) -> None:
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            print(result)
            return
    print(json.dumps(result, indent=2))


async def test_search():
    header(f"Tool 1 · cdc_search_datasets  query='{SEARCH_QUERY}'")
    data = await client.catalog_search(SEARCH_QUERY, SEARCH_LIMIT)
    results = data.get("results", [])
    total = data.get("resultSetSize", 0)
    print(f"Total matching datasets: {total}  |  Showing: {len(results)}\n")
    for r in results:
        res = r.get("resource", {})
        print(f"  ID   : {res.get('id')}")
        print(f"  Name : {res.get('name')}")
        print(f"  Desc : {(res.get('description') or '')[:120]}")
        print(f"  Link : {r.get('permalink')}")
        print()


async def test_schema():
    header(f"Tool 2 · cdc_get_dataset_schema  dataset_id='{SCHEMA_DATASET_ID}'")
    meta = await client.dataset_metadata(SCHEMA_DATASET_ID)
    print(f"Name        : {meta.get('name')}")
    print(f"Category    : {meta.get('category')}")
    print(f"Description : {(meta.get('description') or '')[:200]}\n")
    print(f"Columns ({len(meta.get('columns', []))}):")
    for col in meta.get("columns", []):
        cached = col.get("cachedContents", {})
        top = [e.get("item") for e in (cached.get("top") or [])[:3] if e.get("item")]
        print(f"  {col.get('fieldName'):30s}  {col.get('dataTypeName'):12s}  sample={top}")


async def test_query():
    header(
        f"Tool 3 · cdc_query_dataset  dataset_id='{QUERY_DATASET_ID}'\n"
        f"         select={QUERY_SELECT}  where={QUERY_WHERE!r}  order_by={QUERY_ORDER_BY!r}"
    )
    total, rows = await asyncio.gather(
        client.dataset_row_count(QUERY_DATASET_ID, where=QUERY_WHERE),
        client.dataset_query(
            dataset_id=QUERY_DATASET_ID,
            select=QUERY_SELECT,
            where=QUERY_WHERE,
            order_by=QUERY_ORDER_BY,
            limit=QUERY_LIMIT,
        ),
    )
    print(f"Total rows in dataset: {total}  |  Rows returned: {len(rows)}\n")
    show(rows)


async def test_sample():
    header(f"Tool 4 · cdc_get_sample_rows  dataset_id='{SAMPLE_DATASET_ID}'  limit={SAMPLE_LIMIT}")
    rows = await client.dataset_query(SAMPLE_DATASET_ID, limit=SAMPLE_LIMIT)
    if rows:
        print(f"Columns: {list(rows[0].keys())}\n")
    show(rows)


async def main():
    tests = [
        ("search",  test_search),
        ("schema",  test_schema),
        ("query",   test_query),
        ("sample",  test_sample),
    ]

    # Allow running a single tool: python test_tools.py search
    if len(sys.argv) > 1:
        name = sys.argv[1].lower()
        tests = [(n, fn) for n, fn in tests if n == name]
        if not tests:
            print(f"Unknown tool '{name}'. Choose from: search, schema, query, sample")
            sys.exit(1)

    for name, fn in tests:
        try:
            await fn()
        except Exception as exc:
            print(f"\n[ERROR in {name}] {type(exc).__name__}: {exc}")

    print(f"\n{'=' * 60}\nDone.\n")


if __name__ == "__main__":
    asyncio.run(main())
