# etilbudsavis-mcp

Unofficial, read-only MCP server for [eTilbudsavis.dk](https://etilbudsavis.dk/) (Tjek) grocery offers.

Searches current Danish grocery offers from eTilbudsavis through the same batched `POST /` query the
site uses, where each item of `data` is `base64(JSON(["offers", {params}]))`.

## Tools

- `search_offers(query_text, limit=20, offset=0, sort="score_desc", source="publication", include_upcoming=True)`
- `cheapest_offers(query_text, limit=10)`: relevance results sorted by price per kg/litre

## Local use (stdio)

    uv sync
    claude mcp add etilbudsavis -- uv run --directory "$PWD" python server.py

## Docker Compose (streamable HTTP at `/mcp`, behind a reverse proxy)

1. Create the API key: `mkdir -p secrets && python3 -c "import secrets;print(secrets.token_urlsafe(32))" > secrets/mcp_api_key && chmod 600 secrets/*`
2. Edit `compose.yaml`: set `ETILBUDSAVIS_ALLOWED_HOSTS` to your public hostname and make sure the
   container shares a network with your proxy (`PROXY_NETWORK`, default `proxy`).
3. `docker compose up -d --build`
4. Point the proxy at `http://etilbudsavis-mcp:8000`. Turn off any browser-based login on that route;
   the server checks the Bearer key itself.
5. `claude mcp add-json etilbudsavis '{"type":"http","url":"https://tilbud-mcp.example.com/mcp","headers":{"Authorization":"Bearer ${ETILBUDSAVIS_MCP_KEY}"}}'`

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `http` for streamable HTTP (the image sets it) |
| `MCP_API_KEY` / `MCP_API_KEY_FILE` | required in HTTP mode | Bearer key clients must send (min 24 chars) |
| `ETILBUDSAVIS_ALLOWED_HOSTS` | localhost only | Comma-separated Host headers to accept |
| `ETILBUDSAVIS_ALLOWED_ORIGINS` | localhost only | Comma-separated allowed Origins (browser clients) |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Proxy addresses whose `X-Forwarded-*` headers are trusted |
| `RATE_LIMIT_PER_MIN` | `120` | Global request limit |
| `AUTH_FAIL_LIMIT_PER_MIN` | `10` | Failed-auth attempts per minute before everything is refused for a while |
| `LOG_LEVEL` | `info` | uvicorn log level |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | HTTP bind address |
| `ETILBUDSAVIS_URL` | `https://etilbudsavis.dk/` | Upstream base URL |

## Security notes

- Offer text comes from third parties and is untrusted; tool descriptions tell the model not to
  follow instructions found in it.
- The server is read-only and holds no upstream credentials.
- Every container on the shared proxy network can reach this server; prefer a network shared only
  with the proxy.
- The failed-auth limiter is global: repeated bad keys can lock you out for up to a minute.
- The image installs exactly what `uv.lock` pins (`uv sync --locked`), and both base images are
  pinned by digest. Dependabot opens weekly PRs for Python packages, Docker images and GitHub
  Actions; CI (`.github/workflows/ci.yml`) runs lint, tests and a container smoke test on each.

## Development

    uv run pytest
    uv run ruff check .
