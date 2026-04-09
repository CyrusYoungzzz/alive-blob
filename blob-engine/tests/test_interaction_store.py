import json
import tempfile
from pathlib import Path

from interaction_store import InteractionStore


def test_increment_new_character():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("cube")
        assert store.get_count("cube") == 1


def test_increment_existing_character():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("cube")
        store.increment("cube")
        store.increment("cube")
        assert store.get_count("cube") == 3


def test_rankings_sorted_by_count_desc():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        for _ in range(5):
            store.increment("a")
        for _ in range(10):
            store.increment("b")
        for _ in range(3):
            store.increment("c")
        rankings = store.get_rankings()
        assert rankings[0]["name"] == "b"
        assert rankings[0]["rank"] == 1
        assert rankings[1]["name"] == "a"
        assert rankings[2]["name"] == "c"


def test_persistence_across_instances():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "interactions.json"
        store1 = InteractionStore(path)
        store1.increment("cube")
        store1.increment("cube")
        store1.flush()

        store2 = InteractionStore(path)
        assert store2.get_count("cube") == 2


def test_total_count():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("a")
        store.increment("b")
        store.increment("b")
        assert store.get_total() == 3


def test_last_hit_timestamp():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("cube")
        assert store.last_hit_ts is not None
