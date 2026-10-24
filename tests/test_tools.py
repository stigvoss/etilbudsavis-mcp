import base64
import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

pytestmark = pytest.mark.anyio

OFFER = {
    "publicId": "x",
    "name": "Smør",
    "price": 15,
    "unitPrice": 75,
    "currencyCode": "DKK",
    "business": {"name": "Netto"},
}


def _mock(server, handler):
    server._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok(offers):
    def handler(request):
        return httpx.Response(200, text=json.dumps({"key": "k", "status": "success", "value": {"data": offers}}))

    return handler


def test_encode_query_roundtrip(load_server):
    key = load_server().encode_query("offers", {"searchTerm": "smør"})
    assert json.loads(base64.b64decode(key)) == ["offers", {"searchTerm": "smør"}]


def test_slim_offer_handles_missing_business(load_server):
    assert load_server().slim_offer({"publicId": "x", "price": 1})["store"] is None


async def test_search_offers_sends_query_and_trims(load_server):
    server = load_server()
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return _ok([OFFER])(request)

    _mock(server, handler)
    result = await server.search_offers("smør", limit=500)
    assert result[0]["store"] == "Netto" and result[0]["unit_price"] == 75
    kind, params = json.loads(base64.b64decode(seen["body"]["data"][0]))
    assert kind == "offers" and params["searchTerm"] == "smør" and params["pagination"]["limit"] == 50


async def test_cheapest_offers_sorts_by_unit_price(load_server):
    server = load_server()
    offers = [{**OFFER, "name": "dyr", "unitPrice": 90}, {**OFFER, "name": "billig", "unitPrice": 10},
              {**OFFER, "name": "ukendt", "unitPrice": None}]
    _mock(server, _ok(offers))
    assert [o["name"] for o in await server.cheapest_offers("x", limit=5)] == ["billig", "dyr"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503),
        httpx.Response(200, text="not json"),
        httpx.Response(200, text=json.dumps({"status": "error"})),
        httpx.Response(200, text=json.dumps({"status": "success", "value": {}})),
    ],
)
async def test_upstream_problems_become_tool_errors(load_server, response):
    server = load_server()
    _mock(server, lambda request: response)
    with pytest.raises(ToolError):
        await server.search_offers("smør")


async def test_network_failure_becomes_tool_error(load_server):
    server = load_server()

    def handler(request):
        raise httpx.ConnectError("boom")

    _mock(server, handler)
    with pytest.raises(ToolError, match="Could not reach"):
        await server.search_offers("smør")
