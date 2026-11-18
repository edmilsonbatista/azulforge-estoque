import os
import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.models import Product, ProductInput


class ProductStore(Protocol):
    def list_products(self) -> list[Product]: ...

    def get_product(self, product_id: str) -> Product | None: ...

    def create_product(self, product: ProductInput) -> Product: ...

    def update_product(
        self, product_id: str, product: ProductInput
    ) -> Product | None: ...

    def delete_product(self, product_id: str) -> bool: ...


class SQLiteProductStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    category TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _product(row: sqlite3.Row) -> Product:
        return Product.model_validate(dict(row))

    def list_products(self) -> list[Product]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM products ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._product(row) for row in rows]

    def get_product(self, product_id: str) -> Product | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
        return self._product(row) if row else None

    def create_product(self, product: ProductInput) -> Product:
        created = Product(id=str(uuid4()), **product.model_dump())
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO products (id, name, sku, quantity, category, description)
                VALUES (:id, :name, :sku, :quantity, :category, :description)
                """,
                created.model_dump(),
            )
        return created

    def update_product(
        self, product_id: str, product: ProductInput
    ) -> Product | None:
        updated = Product(id=product_id, **product.model_dump())
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                """
                UPDATE products
                SET name = :name, sku = :sku, quantity = :quantity,
                    category = :category, description = :description
                WHERE id = :id
                """,
                updated.model_dump(),
            )
        return updated if result.rowcount else None

    def delete_product(self, product_id: str) -> bool:
        with closing(self._connect()) as connection, connection:
            result = connection.execute(
                "DELETE FROM products WHERE id = ?", (product_id,)
            )
        return result.rowcount > 0


class CosmosProductStore:
    def __init__(self, endpoint: str, database: str, container: str) -> None:
        from azure.cosmos import CosmosClient
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        from azure.identity import DefaultAzureCredential

        self._not_found_error: type[Exception] = CosmosResourceNotFoundError
        client = CosmosClient(endpoint, credential=DefaultAzureCredential())
        self.container = client.get_database_client(database).get_container_client(
            container
        )

    def list_products(self) -> list[Product]:
        documents = self.container.query_items(
            query="SELECT * FROM c", enable_cross_partition_query=True
        )
        return [Product.model_validate(document) for document in documents]

    def get_product(self, product_id: str) -> Product | None:
        try:
            document = self.container.read_item(
                item=product_id, partition_key=product_id
            )
        except self._not_found_error:
            return None
        return Product.model_validate(document)

    def create_product(self, product: ProductInput) -> Product:
        created = Product(id=str(uuid4()), **product.model_dump())
        self.container.create_item(body=created.model_dump())
        return created

    def update_product(
        self, product_id: str, product: ProductInput
    ) -> Product | None:
        updated = Product(id=product_id, **product.model_dump())
        try:
            self.container.replace_item(
                item=product_id, body=updated.model_dump(), partition_key=product_id
            )
        except self._not_found_error:
            return None
        return updated

    def delete_product(self, product_id: str) -> bool:
        try:
            self.container.delete_item(item=product_id, partition_key=product_id)
        except self._not_found_error:
            return False
        return True


@lru_cache(maxsize=1)
def get_store() -> ProductStore:
    backend = os.getenv("STORAGE_BACKEND", "sqlite").lower()
    if backend == "sqlite":
        environment = os.getenv("APP_ENV", "dev")
        directory = Path(os.getenv("DATABASE_DIR", "data"))
        return SQLiteProductStore(directory / f"{environment}.sqlite3")
    if backend == "cosmos":
        endpoint = os.getenv("COSMOS_ENDPOINT")
        database = os.getenv("COSMOS_DATABASE")
        container = os.getenv("COSMOS_CONTAINER")
        if not endpoint or not database or not container:
            raise RuntimeError(
                "COSMOS_ENDPOINT, COSMOS_DATABASE e COSMOS_CONTAINER "
                "são obrigatórios para STORAGE_BACKEND=cosmos."
            )
        return CosmosProductStore(endpoint, database, container)
    raise RuntimeError(f"STORAGE_BACKEND não suportado: {backend}")
