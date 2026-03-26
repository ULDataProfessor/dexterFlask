from __future__ import annotations


def test_memory_search_bm25_finds_unique_token() -> None:
    from dexter_flask.memory.manager import MemoryManager
    from dexter_flask.memory.store import LONG_TERM, MemoryStore

    store = MemoryStore()
    prev = store.read_file(LONG_TERM)
    try:
        token = "ZEBRA_UNIQUE_TOKEN_12345"
        store.write_file(LONG_TERM, f"Some notes about zebras: {token}.\n")

        mm = MemoryManager.get()
        results = mm.search(f"Find information about {token}", max_results=3)
        assert results
        assert results[0]["file_path"] == LONG_TERM
        assert token in results[0]["snippet"]
    finally:
        store.write_file(LONG_TERM, prev)
