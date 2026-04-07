import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from server.main import create_app

@pytest.fixture
def client(tmp_path):
    app = create_app(characters_dir=tmp_path / "characters")
    return TestClient(app)

def test_list_characters_empty(client):
    resp = client.get("/api/characters")
    assert resp.status_code == 200
    assert resp.json() == []

def test_create_character_with_photo(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    resp = client.post(
        "/api/characters",
        data={"name": "test-boss"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-boss"
    assert data["status"] == "generating"

def test_list_characters_after_create(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client.post(
        "/api/characters",
        data={"name": "boss"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    resp = client.get("/api/characters")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "boss" in names

def test_get_character_detail(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client.post(
        "/api/characters",
        data={"name": "detail-test"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    resp = client.get("/api/characters/detail-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "detail-test"
    assert "emotions" in data

def test_delete_character(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client.post(
        "/api/characters",
        data={"name": "to-delete"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    resp = client.delete("/api/characters/to-delete")
    assert resp.status_code == 200

    resp = client.get("/api/characters/to-delete")
    assert resp.status_code == 404

def test_status_endpoint(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert "ok" in resp.json()["status"]
