from pathlib import Path
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse

from app.models import Product, ProductInput
from app.storage import ProductStore, get_store

app = FastAPI(title="AzulForge Estoque", version="1.0.0")
INDEX_FILE = Path(__file__).parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(INDEX_FILE)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "environment": os.getenv("APP_ENV", "dev")}


@app.get("/api/products", response_model=list[Product])
def list_products(store: ProductStore = Depends(get_store)) -> list[Product]:
    return store.list_products()


@app.post(
    "/api/products", response_model=Product, status_code=status.HTTP_201_CREATED
)
def create_product(
    product: ProductInput, store: ProductStore = Depends(get_store)
) -> Product:
    return store.create_product(product)


@app.get("/api/products/{product_id}", response_model=Product)
def get_product(
    product_id: str, store: ProductStore = Depends(get_store)
) -> Product:
    product = store.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return product


@app.put("/api/products/{product_id}", response_model=Product)
def update_product(
    product_id: str,
    product: ProductInput,
    store: ProductStore = Depends(get_store),
) -> Product:
    updated = store.update_product(product_id, product)
    if updated is None:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return updated


@app.delete("/api/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str, store: ProductStore = Depends(get_store)
) -> None:
    if not store.delete_product(product_id):
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
