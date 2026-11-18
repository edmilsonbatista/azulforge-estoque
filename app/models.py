from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=0)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=1000)

    @field_validator("name", "sku", "category")
    @classmethod
    def reject_blank_values(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Este campo não pode ficar vazio.")
        return normalized


class Product(ProductInput):
    id: str
