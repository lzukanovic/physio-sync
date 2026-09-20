import pytest
from fastapi.testclient import TestClient

from physiosync import __version__, config
from physiosync.api.app import create_app


@pytest.fixture
def web(tmp_path):
    d = tmp_path / "web"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<div id=root>spa</div>")
    (d / "assets" / "app.js").write_text("//js")
    return d


@pytest.fixture
def client(tmp_path, web):
    settings = config.load({"PHYSIOSYNC_DATA": str(tmp_path / "data")})
    with TestClient(create_app(settings, web_dir=web)) as c:  # context: runs lifespan
        yield c


def test_health(client, tmp_path):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == __version__
    assert body["db_ok"] is True
    assert body["data_root"] == str((tmp_path / "data").resolve())
    assert (tmp_path / "data" / "physiosync.db").is_file()


def test_spa_fallback_on_client_route(client):
    for path in ("/", "/studies", "/takes/abc"):
        r = client.get(path)
        assert r.status_code == 200 and "spa" in r.text, path
    assert client.get("/assets/app.js").text == "//js"


def test_unknown_api_and_missing_asset_stay_404(client):
    assert client.get("/api/nope").status_code == 404
    assert client.get("/assets/missing.js").status_code == 404


def test_starts_without_built_frontend(tmp_path):
    settings = config.load({"PHYSIOSYNC_DATA": str(tmp_path)})
    with TestClient(create_app(settings, web_dir=tmp_path / "absent")) as c:
        assert c.get("/api/health").status_code == 200
