"""ORION custom database types and pgvector dialect compatibility."""

import json
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class CompatibleVector(TypeDecorator):
    """A vector type decorator that renders pgvector's Vector(dim) on PostgreSQL

    and falls back to JSON-serialized floats on SQLite for offline testing.
    """

    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 384, **kwargs: Any):
        super().__init__(**kwargs)
        self.dim = dim
        self._pg_vector = Vector(dim)

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(self._pg_vector)
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any | None, dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            # pgvector handles numpy arrays and lists directly
            if hasattr(value, "tolist"):
                return value.tolist()
            return value
        # SQLite fallback: store as JSON string
        if hasattr(value, "tolist"):
            return json.dumps(value.tolist())
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value))
        return value

    def process_result_value(self, value: Any | None, dialect: Any) -> list[float] | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            if hasattr(value, "tolist"):
                return value.tolist()
            return list(value)
        # SQLite fallback: parse JSON string
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return []
        return value
