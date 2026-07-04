from pathlib import Path


def test_compose_exposes_print_updates_env() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")

    assert "BESTELLBAR_PRINT_UPDATES: ${BESTELLBAR_PRINT_UPDATES:-false}" in compose
