"""
Async HTTP client for the three Socrata API surfaces on data.cdc.gov:
  1. Catalog API  — /api/catalog/v1
  2. Metadata API — /api/views/{dataset_id}.json
  3. Data API     — /resource/{dataset_id}.json
"""

import os
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://data.cdc.gov"
CATALOG_URL = f"{BASE_URL}/api/catalog/v1"
TIMEOUT = float(os.getenv("CDC_TIMEOUT_SECONDS", "30"))


def _headers() -> dict[str, str]:
    token = os.getenv("CDC_APP_TOKEN", "")
    if token:
        return {"X-App-Token": token}
    return {}


async def catalog_search(query: str, limit: int = 5) -> dict[str, Any]:
    """Search the CDC dataset catalog using the q= parameter."""
    params = {
        "q": query,
        "only": "datasets",
        "limit": limit,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(CATALOG_URL, params=params, headers=_headers())
        response.raise_for_status()
        return response.json()


async def dataset_metadata(dataset_id: str) -> dict[str, Any]:
    """Fetch full metadata for a dataset, including column definitions."""
    url = f"{BASE_URL}/api/views/{dataset_id}.json"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, headers=_headers())
        response.raise_for_status()
        return response.json()


async def dataset_query(
    dataset_id: str,
    select: list[str] | None = None,
    where: str | None = None,
    group_by: list[str] | None = None,
    order_by: str | None = None,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """Execute a SoQL query against a dataset and return rows as JSON."""
    url = f"{BASE_URL}/resource/{dataset_id}.json"
    params: dict[str, Any] = {"$limit": limit, "$offset": offset}

    if select:
        params["$select"] = ", ".join(select)
    if where:
        params["$where"] = where
    if group_by:
        params["$group"] = ", ".join(group_by)
    if order_by:
        params["$order"] = order_by
    if search:
        params["$search"] = search

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params=params, headers=_headers())
        response.raise_for_status()
        return response.json()


async def dataset_row_count(
    dataset_id: str,
    where: str | None = None,
    search: str | None = None,
) -> int:
    """Return the total number of rows matching the given filters (fast count query)."""
    url = f"{BASE_URL}/resource/{dataset_id}.json"
    params: dict[str, Any] = {"$select": "count(*) AS total", "$limit": 1}
    if where:
        params["$where"] = where
    if search:
        params["$search"] = search

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params=params, headers=_headers())
        response.raise_for_status()
        data = response.json()
        if data and "total" in data[0]:
            return int(data[0]["total"])
        return 0
