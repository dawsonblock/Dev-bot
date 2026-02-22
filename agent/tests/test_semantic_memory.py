import os
import shutil
from memory.vector_store import VectorStore


def test_semantic_retrieval():
    """Verify that the neural embedding model can retrieve concepts by meaning, not just exact keywords."""

    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), ".test-chroma-db")
    )
    if os.path.exists(db_path):
        shutil.rmtree(db_path)

    vs = VectorStore(persist_directory=db_path)

    # Add various technical contexts
    vs.add(
        "The database connection pool is exhausted, causing timeouts.",
        {"type": "error"},
    )
    vs.add("User authentication failed due to expired JWT token.", {"type": "security"})
    vs.add("The API rate limit was exceeded for the payment gateway.", {"type": "api"})
    vs.add(
        "Garbage collection is pausing the JVM for too long.", {"type": "performance"}
    )

    # Query 1: Semantic match for "database" issues without using the exact words
    res1 = vs.search("SQL connections are maxed out", k=1)
    assert len(res1) == 1
    assert "pool is exhausted" in res1[0]

    # Query 2: Semantic match for "auth tokens"
    res2 = vs.search("login restricted because session claims are invalid", k=1)
    assert len(res2) == 1
    assert "JWT token" in res2[0]

    # Query 3: Match memory management issues
    res3 = vs.search("Java memory cleanup is blocking threads", k=1)
    assert len(res3) == 1
    assert "JVM" in res3[0]

    # Cleanup
    shutil.rmtree(db_path)
