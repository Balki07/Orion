"""Pytest configuration and test fixtures for ORION backend."""

import os
import sys
from pathlib import Path
from typing import AsyncGenerator

# Ensure backend root is on sys.path
backend_dir = str(Path(__file__).resolve().parent.parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure test environment variables before importing app
test_db_path = Path("./storage/test_orion_suite.db").resolve()
test_db_path.parent.mkdir(parents=True, exist_ok=True)
db_url = f"sqlite+aiosqlite:///{test_db_path.as_posix()}"

os.environ["ORION_ENV"] = "development"
os.environ["DEV_AUTH_BYPASS"] = "true"
os.environ["STORAGE_PROVIDER"] = "local"
os.environ["STORAGE_LOCAL_DIR"] = "./storage/test_uploads"
os.environ["DATABASE_URL"] = db_url

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.base import Base
import app.db.session as session_module
from app.db.session import get_db
from app.main import app

test_engine = create_async_engine(
    db_url,
    connect_args={"check_same_thread": False},
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Monkey-patch session_module.AsyncSessionLocal so background tasks use test db
session_module.AsyncSessionLocal = TestSessionLocal


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Generates a valid 2-page research PDF containing known verifiable wrapped text."""
    doc = pymupdf.open()
    rect = pymupdf.Rect(50, 50, 550, 750)

    # Page 1
    p1 = doc.new_page(width=595, height=842)
    p1_text = (
        "Title: Attention Is All You Need\n\n"
        "Abstract: The dominant sequence transduction models are based on complex recurrent or convolutional "
        "neural networks that include an encoder and a decoder. We propose a new simple network architecture, "
        "the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.\n\n"
        "Section 1: Introduction\n"
        "Recurrent neural networks, long short-term memory and gated recurrent neural networks have been firmly "
        "established as state of the art approaches in sequence modeling and transduction problems such as language "
        "modeling and machine translation."
    )
    p1.insert_textbox(rect, p1_text, fontsize=11)

    # Page 2
    p2 = doc.new_page(width=595, height=842)
    p2_text = (
        "Section 3.2: Scaled Dot-Product Attention\n\n"
        "We compute the attention function on a set of queries simultaneously, packed together into a matrix Q. "
        "The keys and values are also packed together into matrices K and V. We compute the matrix of outputs as: "
        "Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V.\n\n"
        "Section 6: Results\n"
        "On the WMT 2014 English-to-German translation task, the big transformer model achieves a state-of-the-art "
        "BLEU score of 28.4, outperforming the best existing models."
    )
    p2.insert_textbox(rect, p2_text, fontsize=11)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
