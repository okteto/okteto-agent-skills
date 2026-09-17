from app import app


def test_health():
    client = app.test_client()
    assert client.get("/health").data == b"ok"
