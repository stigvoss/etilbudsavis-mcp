"""Unofficial MCP server for eTilbudsavis.dk.

The site's front end posts batched queries to ``POST /`` where each item of
``data`` is base64(JSON(["offers", {params}])). This server replays that call, read-only.
Transport: stdio by default, or streamable HTTP with ``MCP_TRANSPORT=http`` (optional Bearer
check via ``MCP_API_KEY`` or ``MCP_API_KEY_FILE``).
"""

import base64
import hmac
import json
import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

BASE_URL = os.environ.get("ETILBUDSAVIS_URL", "https://etilbudsavis.dk/")
HEADERS = {"user-agent": "etilbudsavis-mcp/0.1 (personal use)", "content-type": "application/json"}

# Host-header allow-list (DNS-rebinding protection); list the public hostname behind a proxy.
TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"]
    + [h for h in os.environ.get("ETILBUDSAVIS_ALLOWED_HOSTS", "").split(",") if h],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
)

mcp = MCPServer("etilbudsavis")


def encode_query(kind: str, params: dict[str, Any]) -> str:
    raw = json.dumps([kind, params], separators=(",", ":"), ensure_ascii=False)
    return base64.b64encode(raw.encode()).decode()


def slim_offer(o: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": o.get("publicId"),
        "name": o.get("name"),
        "description": o.get("description"),
        "price": o.get("price"),
        "currency": o.get("currencyCode"),
        "unit_price": o.get("unitPrice"),
        "base_unit": o.get("baseUnit"),
        "store": (o.get("business") or {}).get("name"),
        "valid_from": o.get("validFrom"),
        "valid_until": o.get("validUntil"),
        "image": o.get("image"),
    }


async def query(kind: str, params: dict[str, Any]) -> Any:
    key = encode_query(kind, params)
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        resp = await client.post(BASE_URL, json={"data": [key]})
    resp.raise_for_status()
    item = json.loads(resp.text.splitlines()[0])
    if item.get("status") != "success":
        raise RuntimeError(f"eTilbudsavis query failed: {item}")
    return item["value"]["data"]


@mcp.tool()
async def search_offers(
    query_text: str,
    limit: int = 20,
    offset: int = 0,
    sort: str = "score_desc",
    source: str = "publication",
    include_upcoming: bool = True,
) -> list[dict[str, Any]]:
    """Search current Danish grocery offers (tilbud).

    source: "publication" (leaflet offers) or "business_product" (always-on store products).
    sort: "score_desc" (relevance); other values are passed through to the site.
    Returns name, price (DKK), unit_price per base_unit, store and validity window.
    """
    data = await query(
        "offers",
        {
            "hideUpcoming": not include_upcoming,
            "pagination": {"limit": max(1, min(limit, 50)), "offset": max(0, offset)},
            "searchTerm": query_text,
            "sort": [sort],
            "sources": [source],
        },
    )
    return [slim_offer(o) for o in data]


@mcp.tool()
async def cheapest_offers(query_text: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search offers and return them sorted by price per base unit (kg/litre), cheapest first."""
    offers = await search_offers(query_text, limit=50)
    priced = [o for o in offers if o["unit_price"] is not None]
    return sorted(priced, key=lambda o: o["unit_price"])[: max(1, limit)]


def main() -> None:
    if os.environ.get("MCP_TRANSPORT", "stdio") != "http":
        mcp.run()
        return
    import uvicorn

    api_key = os.environ.get("MCP_API_KEY", "")
    if key_file := os.environ.get("MCP_API_KEY_FILE"):
        api_key = Path(key_file).read_text().strip()
    host = os.environ.get("HOST", "0.0.0.0")
    app = mcp.streamable_http_app(transport_security=TRANSPORT_SECURITY, host=host)

    async def gated(scope, receive, send):
        if scope["type"] == "http" and api_key:
            headers = dict(scope["headers"])
            presented = headers.get(b"authorization", b"").decode().removeprefix("Bearer ")
            if not hmac.compare_digest(presented.encode(), api_key.encode()):
                await send({"type": "http.response.start", "status": 401, "headers": [(b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b""})
                return
        await app(scope, receive, send)

    uvicorn.run(gated, host=host, port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
