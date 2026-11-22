import os
import sys

os.environ.setdefault("LIGHTFOOT_MOCK", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from lightfoot.embed import Embedder
from lightfoot.retrieve import Reranker


@pytest.fixture(scope="session")
def embedder():
    return Embedder()


@pytest.fixture(scope="session")
def reranker():
    try:
        r = Reranker()
        r.score("warm up", ["hello"])
        return r
    except Exception as e:  # pragma: no cover - offline fallback
        pytest.skip(f"reranker unavailable: {e}")


@pytest.fixture
def tmp_cache(tmp_path):
    return str(tmp_path / "cache")
