import base64
import json

from server import encode_query, slim_offer


def test_encode_query_roundtrip():
    key = encode_query("offers", {"searchTerm": "smør"})
    assert json.loads(base64.b64decode(key)) == ["offers", {"searchTerm": "smør"}]


def test_slim_offer_handles_missing_business():
    assert slim_offer({"publicId": "x", "price": 1})["store"] is None
