from pathlib import Path

from bestellbar_bot.config import AppConfig
from bestellbar_bot.monitor import check_once
from bestellbar_bot.notifiers.base import NotificationError
from bestellbar_bot.parser import ParseError, Update
from bestellbar_bot.state import load_state


class CollectingNotifier:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.updates: list[Update] = []
        self.fail_after = fail_after

    def send_update(self, update: Update) -> None:
        if self.fail_after is not None and len(self.updates) >= self.fail_after:
            raise NotificationError("notification failed")
        self.updates.append(update)


def _cfg(
    tmp_path: Path,
    *,
    notify_existing: bool = False,
    dry_run: bool = False,
) -> AppConfig:
    return AppConfig(
        url="https://example.com/product",
        state_file=tmp_path / "state.json",
        interval_seconds=60,
        timeout_seconds=15,
        user_agent="test",
        notify_existing=notify_existing,
        dry_run=dry_run,
        print_updates=False,
        pushover_token="token",
        pushover_user_key="user",
        pushover_device=None,
    )


def _update(fingerprint: str, title: str) -> Update:
    return Update(
        fingerprint=fingerprint,
        kind="info",
        title=title,
        summary=f"{title} body",
        timestamp_text="",
        source_text="",
        url="",
    )


def test_check_once_seeds_state_without_notifying_on_first_run(tmp_path: Path) -> None:
    notifier = CollectingNotifier()
    updates = [_update("a", "Old")]
    handled: list[Update] = []

    result = check_once(
        _cfg(tmp_path),
        notifier,
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: updates,
        update_handler=handled.append,
    )

    assert result.success is True
    assert result.seeded_updates == 1
    assert notifier.updates == []
    assert handled == []
    assert load_state(tmp_path / "state.json").known_fingerprints == {"a"}


def test_check_once_notifies_only_new_updates(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    first_updates = [_update("a", "Old")]
    check_once(
        cfg,
        CollectingNotifier(),
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: first_updates,
    )
    notifier = CollectingNotifier()
    second_updates = [_update("b", "New"), _update("a", "Old")]
    handled: list[Update] = []

    result = check_once(
        cfg,
        notifier,
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: second_updates,
        update_handler=handled.append,
    )

    assert result.success is True
    assert result.new_updates == 1
    assert [update.title for update in notifier.updates] == ["New"]
    assert [update.title for update in handled] == ["New"]
    assert load_state(tmp_path / "state.json").known_fingerprints == {"a", "b"}


def test_check_once_notifies_multiple_updates_in_oldest_first_order(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path, notify_existing=True)
    notifier = CollectingNotifier()
    updates_newest_first = [_update("c", "Newest"), _update("b", "Middle")]
    handled: list[Update] = []

    result = check_once(
        cfg,
        notifier,
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: updates_newest_first,
        update_handler=handled.append,
    )

    assert result.success is True
    assert [update.title for update in notifier.updates] == ["Middle", "Newest"]
    assert [update.title for update in handled] == ["Middle", "Newest"]


def test_check_once_does_not_advance_failed_notification(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    check_once(
        cfg,
        CollectingNotifier(),
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: [_update("a", "Old")],
    )

    handled: list[Update] = []

    result = check_once(
        cfg,
        CollectingNotifier(fail_after=0),
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: [_update("b", "New"), _update("a", "Old")],
        update_handler=handled.append,
    )

    assert result.success is False
    assert handled == []
    assert load_state(tmp_path / "state.json").known_fingerprints == {"a"}


def test_check_once_calls_handler_in_dry_run_when_notifier_succeeds(
    tmp_path: Path,
) -> None:
    cfg = _cfg(tmp_path, notify_existing=True, dry_run=True)
    notifier = CollectingNotifier()
    handled: list[Update] = []

    result = check_once(
        cfg,
        notifier,
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: [_update("a", "Current")],
        update_handler=handled.append,
    )

    assert result.success is True
    assert [update.title for update in notifier.updates] == ["Current"]
    assert [update.title for update in handled] == ["Current"]
    assert not (tmp_path / "state.json").exists()


def test_check_once_returns_failure_without_corrupting_state(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)

    result = check_once(
        cfg,
        CollectingNotifier(),
        fetch_func=lambda _url, _timeout, _user_agent: "html",
        parse_func=lambda _html, _base_url: (_ for _ in ()).throw(ParseError("boom")),
    )

    assert result.success is False
    assert not (tmp_path / "state.json").exists()
