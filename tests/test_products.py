from fastapi.testclient import TestClient

from app.main import app
from app.models import ProductInput
from app.storage import SQLiteProductStore, get_store


def test_product_lifecycle_uses_sqlite_store(tmp_path):
    store = SQLiteProductStore(tmp_path / "products.sqlite3")
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    try:
        home = client.get("/")
        assert home.status_code == 200
        assert "AzulForge Estoque" in home.text
        assert 'id="environment-badge"' in home.text
        assert client.get("/health").json()["status"] == "ok"

        created = client.post(
            "/api/products",
            json={
                "name": "Caneca",
                "sku": "CNC-01",
                "quantity": 12,
                "category": "Casa",
                "description": "Caneca azul",
            },
        )
        assert created.status_code == 201
        product = created.json()
        product_id = product["id"]

        assert client.get("/api/products").json() == [product]
        assert client.get(f"/api/products/{product_id}").json() == product

        updated = client.put(
            f"/api/products/{product_id}",
            json={
                "name": "Caneca grande",
                "sku": "CNC-01",
                "quantity": 8,
                "category": "Casa",
                "description": "",
            },
        )
        assert updated.status_code == 200
        assert updated.json()["quantity"] == 8
        assert updated.json()["name"] == "Caneca grande"

        assert client.delete(f"/api/products/{product_id}").status_code == 204
        assert client.get(f"/api/products/{product_id}").status_code == 404
        assert client.delete(f"/api/products/{product_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_health_reports_configured_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "hml")

    response = TestClient(app).get("/health")

    assert response.json() == {"status": "ok", "environment": "hml"}


def test_product_rejects_negative_quantity(tmp_path):
    store = SQLiteProductStore(tmp_path / "products.sqlite3")
    app.dependency_overrides[get_store] = lambda: store
    client = TestClient(app)
    try:
        response = client.post(
            "/api/products",
            json={
                "name": "Caneca",
                "sku": "CNC-01",
                "quantity": -1,
                "category": "Casa",
                "description": "",
            },
        )
        assert response.status_code == 422
        assert client.get("/api/products").json() == []
    finally:
        app.dependency_overrides.clear()


def test_local_environments_use_separate_sqlite_files(tmp_path):
    dev_store = SQLiteProductStore(tmp_path / "dev.sqlite3")
    hml_store = SQLiteProductStore(tmp_path / "hml.sqlite3")
    product = {
        "name": "Caneca",
        "sku": "CNC-01",
        "quantity": 12,
        "category": "Casa",
        "description": "",
    }

    dev_store.create_product(ProductInput(**product))

    assert len(dev_store.list_products()) == 1
    assert hml_store.list_products() == []
