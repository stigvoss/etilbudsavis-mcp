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

## Docker

The image is published to GHCR by CI on every push to `main` and is public, so no login is needed to pull it.

    docker run -d --name etilbudsavis-mcp --restart unless-stopped \
      --read-only --cap-drop ALL --security-opt no-new-privileges:true \
      -p 127.0.0.1:8000:8000 \
      -e MCP_API_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" \
      -e ETILBUDSAVIS_ALLOWED_HOSTS="tilbud-mcp.example.com" \
      ghcr.io/stigvoss/etilbudsavis-mcp:latest

Note the generated key (`docker inspect` shows it; use `-e MCP_API_KEY_FILE` with a mounted file to
avoid that). The server is then at `http://127.0.0.1:8000/mcp`, with an unauthenticated `/healthz`.
To build locally instead: `docker build -t etilbudsavis-mcp .` and use that image name.

## Docker Compose (behind a reverse proxy)

Streamable HTTP at `/mcp`. A minimal `compose.yaml` (the one in this repo is the same, with comments):

```yaml
services:
  etilbudsavis-mcp:
    image: ghcr.io/stigvoss/etilbudsavis-mcp:latest
    restart: unless-stopped
    user: "${PUID:-10001}:${PGID:-10001}"   # run as the key file's owner
    environment:
      ETILBUDSAVIS_ALLOWED_HOSTS: "tilbud-mcp.example.com"   # public hostname of the proxy route
      MCP_API_KEY_FILE: /run/secrets/mcp_api_key
    secrets:
      - mcp_api_key
    networks:
      - proxy
    read_only: true
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true

secrets:
  mcp_api_key:
    file: ./secrets/mcp_api_key

networks:
  proxy:
    external: true
    name: ${PROXY_NETWORK:-proxy}   # the Docker network your reverse proxy or tunnel is on
```

1. Create the API key and tell Compose to run the container as the file's owner, so the key can stay
   private (`600`) instead of being made readable to everyone:

       mkdir -p secrets && python3 -c "import secrets;print(secrets.token_urlsafe(32))" > secrets/mcp_api_key
       chmod 600 secrets/mcp_api_key
       printf 'PUID=%s\nPGID=%s\n' "$(id -u)" "$(id -g)" > .env

2. Edit `ETILBUDSAVIS_ALLOWED_HOSTS` and make sure the container shares a network with your proxy
   (`PROXY_NETWORK`, default `proxy`).
3. `docker compose pull && docker compose up -d`. To build locally instead, replace `image:` with `build: .`.
4. Point the proxy at `http://etilbudsavis-mcp:8000`. Turn off any browser-based login on that route;
   the server checks the Bearer key itself.
5. Add it to Claude Code, keeping the key out of shell history via an environment variable:

       export ETILBUDSAVIS_MCP_KEY="$(cat secrets/mcp_api_key)"
       claude mcp add-json etilbudsavis '{"type":"http","url":"https://tilbud-mcp.example.com/mcp","headers":{"Authorization":"Bearer ${ETILBUDSAVIS_MCP_KEY}"}}'

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
  Actions; CI (`.github/workflows/ci.yml`) runs lint, tests and a container smoke test on each, and publishes
  the image to `ghcr.io/stigvoss/etilbudsavis-mcp` from `main`.

## Development

    uv run pytest
    uv run ruff check .
