# data.cdc.gov MCP Server

Ask plain-English questions about US public health data — and get real answers backed by CDC datasets.

This MCP server connects AI clients (Claude Desktop, Claude Code, Cursor, etc.) directly to [data.cdc.gov](https://data.cdc.gov), the CDC's open data portal with ~10,000 datasets covering mortality, disease surveillance, vaccination, chronic illness, environmental health, and more. Instead of downloading CSVs or writing API calls yourself, you just ask.

---

## What you can ask

> *"Which states had the highest obesity rates among adults in 2019?"*

> *"How many provisional drug overdose deaths involved cocaine in Texas in 2022?"*

> *"Compare flu vaccination coverage among adolescents across different years — which year was highest?"*

> *"Is there a relationship between obesity rates and heart disease mortality across US states?"*

> *"What were total COVID-19 deaths in the United States across all age groups?"*

> *"What percentage of high school students smoked cigarettes in New Jersey by race in recent years?"*

The AI handles the dataset discovery, schema lookup, and query construction. You get answers, not raw data dumps.

See [`test-questions.md`](./test-questions.md) for a full set of questions that exercise the complete tool chain, with suggested dataset IDs and test order.

---

## How it works

The server exposes 4 MCP tools that map to the Socrata API:

| Tool | What it does |
|------|--------------|
| `cdc_search_datasets` | Find relevant datasets by topic. Returns IDs, descriptions, column names, and tags. |
| `cdc_get_dataset_schema` | Get full column metadata — field names, types, sample values, min/max ranges. |
| `cdc_get_sample_rows` | Preview raw rows to understand data shape before querying. |
| `cdc_query_dataset` | Run a filtered, grouped, sorted, paginated query against any dataset. |

A typical agent flow looks like this:

```
cdc_search_datasets("opioid overdose deaths by state")
  → cdc_get_dataset_schema("xkb8-kh2a")
    → cdc_get_sample_rows("xkb8-kh2a")           # optional preview
      → cdc_query_dataset("xkb8-kh2a",
            select=["state_name", "indicator", "data_value"],
            where="year = '2022' AND state_name = 'Texas'",
            order_by="data_value DESC")
```

The server validates column names, enforces a hard row cap (default 500) to prevent context flooding, and always returns pagination metadata so the agent can fetch more if needed.

---

## Requirements

- Python 3.11+
- A free [Socrata app token](https://data.cdc.gov/profile/edit/developer_settings) (optional but recommended — without it, requests share a throttled anonymous pool and may hit 429 errors under load)

---

## Installation

```bash
pip install -e .
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
CDC_APP_TOKEN=your_app_token_here   # get one free at data.cdc.gov
CDC_MAX_ROWS=500                    # hard cap on rows per query
CDC_DEFAULT_ROWS=50                 # default when the agent doesn't specify
CDC_TIMEOUT_SECONDS=30              # Socrata API request timeout
```

---

## Adding to your MCP client

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "data-cdc-gov": {
      "command": "/path/to/venv/bin/data-cdc-mcp",
      "env": {
        "CDC_APP_TOKEN": "your_app_token_here"
      }
    }
  }
}
```

Restart Claude Desktop — the 4 CDC tools appear automatically.

### Claude Code CLI

```bash
claude mcp add data-cdc-gov /path/to/venv/bin/python -m cdc_mcp.server
```

### Other MCP clients (Cursor, Windsurf, etc.)

Any client that supports stdio MCP servers works. Point `command` at the `data-cdc-mcp` executable (or `python -m cdc_mcp.server`) and pass env vars as needed.

---

## Production deployment (Streamable HTTP)

Use the `serve` subcommand to run as an HTTP server:

```bash
data-cdc-mcp serve                          # binds to 0.0.0.0:8000
data-cdc-mcp serve --port 9000
data-cdc-mcp serve --host 127.0.0.1 --port 9000
```

MCP clients connect via URL:

```json
{
  "mcpServers": {
    "data-cdc-gov": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Deploying to Azure App Service

1. Set startup command: `data-cdc-mcp serve`
2. Add environment variables under Configuration:
   - `CDC_APP_TOKEN`
   - `CDC_MAX_ROWS` (optional)
   - `CDC_DEFAULT_ROWS` (optional)
3. Set `WEBSITES_PORT=8000` (or pass `--port` to match)

---

## Development

Install in editable mode and open the FastMCP dev UI for interactive tool testing:

```bash
pip install -e .
fastmcp dev src/cdc_mcp/server.py
```

This opens a browser UI where you can call each tool manually and inspect responses.

---

## Project structure

```
src/cdc_mcp/
  server.py        # FastMCP tool definitions and entry point
  client.py        # Async httpx client for the Socrata API
.env.example       # Environment variable template
test-questions.md  # Natural-language test questions with dataset IDs
```

---

## License

MIT
