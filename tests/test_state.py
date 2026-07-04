import json
from pathlib import Path

import pytest

from bestellbar_bot.state import BotState, StateError, load_state, save_state


def test_load_state_missing_file_returns_empty_state(tmp_path: Path) -> None:
    state = load_state(tmp_path / "missing.json")

    assert state.known_fingerprints == set()
    assert state.last_success_at is None


def test_save_state_round_trips_known_fingerprints(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    save_state(path, BotState({"b", "a"}, "2026-07-04T12:00:00+00:00"))

    loaded = load_state(path)

    assert loaded.known_fingerprints == {"a", "b"}
    assert loaded.last_success_at == "2026-07-04T12:00:00+00:00"


def test_load_state_raises_for_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(StateError, match="valid JSON"):
        load_state(path)


def test_save_state_writes_valid_json_atomically(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "state.json"
    save_state(path, BotState({"abc"}))

    raw = json.loads(path.read_text(encoding="utf-8"))

    assert raw["schema_version"] == 1
    assert raw["known_fingerprints"] == ["abc"]
    assert not list(path.parent.glob("*.tmp"))
