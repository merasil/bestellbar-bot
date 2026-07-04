# bestellbar-bot

Small Python CLI that monitors the Bestell.bar product page for the Midea
PortaSplit Online Updates section and sends push notifications through
Pushover.

## Setup

```bash
python -m pip install -e '.[dev]'
export PUSHOVER_API_TOKEN='your-application-token'
export PUSHOVER_USER_KEY='your-user-key'
```

Pushover setup:

1. Install the Pushover iPhone app.
2. Create an application at <https://pushover.net/apps/build>.
3. Export the application token as `PUSHOVER_API_TOKEN`.
4. Export your user key as `PUSHOVER_USER_KEY`.
5. Optionally set `PUSHOVER_DEVICE` to target one device.

## Usage

Run a single check:

```bash
bestellbar-bot check
```

Run continuously:

```bash
bestellbar-bot watch --interval 60
```

Print new updates to stdout:

```bash
bestellbar-bot watch --print-updates
```

Dry-run without Pushover credentials:

```bash
bestellbar-bot check --dry-run --state-file ./bestellbar-bot-state.json
```

The first non-dry run seeds the current Online Updates without sending
notifications. Use `--notify-existing` if existing visible updates should also
be sent. Printing is independent from the Pushover transport but follows the
same new-update detection: `--print-updates` prints one line for each newly
handled update only. The first-run seed without `--notify-existing` is quiet,
and already-known updates are not printed again.

## Docker Compose

Create a local environment file and fill in your Pushover credentials:

```bash
cp .env.example .env
```

Docker Compose reads `.env` automatically for the values in `compose.yaml`.
Exported shell variables with the same names can also be used to override
those values.

Start the bot in watch mode:

```bash
docker compose up -d --build
```

Follow logs:

```bash
docker compose logs -f
```

Set `BESTELLBAR_PRINT_UPDATES=true` in `.env` to print newly handled Online
Updates to stdout, which makes them visible in `docker compose logs -f` without
changing the container command. Output uses one line per update, for example
`04.07.26, 07:48 Uhr - Bestellbar bei Amazon DE Midea PortaSplit Pfirsich 899,10€`.

Stop the bot:

```bash
docker compose down
```

The Compose service stores bot state in the named volume
`bestellbar-bot-state` at `/data/state.json` inside the container by setting
`BESTELLBAR_STATE_FILE=/data/state.json`. Rebuilding the image or running
`docker compose down` keeps that volume. Remove the state intentionally with:

```bash
docker compose down -v
```

Run a one-shot dry run without Pushover credentials:

```bash
docker compose run --rm bestellbar-bot bestellbar-bot check --dry-run --state-file /tmp/state.json
```

On the first non-dry run, the bot seeds the currently visible Online Updates
without sending notifications. Add `--notify-existing` to a manual command if
those existing updates should be sent as notifications. With print mode enabled,
only newly handled updates are printed. Seeded and already-known updates stay
quiet.

## Configuration

CLI options override environment variables.

| Setting | Environment variable | Default |
| --- | --- | --- |
| Product URL | `BESTELLBAR_URL` | `https://www.bestell.bar/p/MTpH/midea-portasplit` |
| State file | `BESTELLBAR_STATE_FILE` | `$XDG_STATE_HOME/bestellbar-bot/state.json` or `~/.local/state/bestellbar-bot/state.json` |
| Poll interval | `BESTELLBAR_INTERVAL` | `60` |
| Request timeout | `BESTELLBAR_TIMEOUT` | `15` |
| User agent | `BESTELLBAR_USER_AGENT` | `bestellbar-bot/0.1 (+https://www.bestell.bar/)` |
| Print new updates to stdout | `BESTELLBAR_PRINT_UPDATES` | `false` |
| Pushover token | `PUSHOVER_API_TOKEN` | required unless `--dry-run` |
| Pushover user key | `PUSHOVER_USER_KEY` | required unless `--dry-run` |
| Pushover device | `PUSHOVER_DEVICE` | optional |

## systemd user service

Example `~/.config/systemd/user/bestellbar-bot.service`:

```ini
[Unit]
Description=Bestell.bar update monitor

[Service]
Environment=PUSHOVER_API_TOKEN=your-application-token
Environment=PUSHOVER_USER_KEY=your-user-key
ExecStart=%h/.local/bin/bestellbar-bot watch --interval 60
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable it with:

```bash
systemctl --user daemon-reload
systemctl --user enable --now bestellbar-bot.service
```
