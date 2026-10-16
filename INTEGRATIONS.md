# Making your bot send the stickers

Adding a set to Telegram puts it in your own sticker tray. Nice, but the point of this
repository is the other direction: your agent's bot picking a sticker and sending it to you on
its own, the moment it finishes something or needs your yes.

One rule shapes everything below. Telegram gives every bot its own `file_id` for the same
sticker, and a `file_id` from one bot does not work for another (Telegram's Bot API docs say so
for every file). So nobody can hand you ids that work. Your bot asks Telegram for the set once
(`getStickerSet`, with your bot's token) and gets ids that are valid for it.

## Hermes Agent

The plugin in [`hermes-plugin/`](hermes-plugin/README.md) does all of it. Hermes has no built-in
"send this sticker" action, but a Hermes plugin can watch the agent's finished reply and call
Telegram itself, which is what this one does:

```sh
hermes plugins install MichaelZelbel/godspeed-stickers/hermes-plugin --enable
hermes gateway restart
```

Your agent ends a reply with `[[sticker:done]]`; the plugin looks the set up through your bot
(once, then it remembers), sends the sticker silently, and removes the tag before the words go
out. It uses the token your Hermes Telegram gateway already has.

## OpenCLAW

OpenCLAW can send stickers by itself. Three steps:

**1. Switch the sticker action on** in `~/.openclaw/openclaw.json`:

```json5
{ channels: { telegram: { actions: { sticker: true } } } }
```

**2. Get the ids for your bot.** Run this with the token of the bot OpenCLAW uses:

```sh
git clone https://github.com/MichaelZelbel/godspeed-stickers && cd godspeed-stickers
BOT_TOKEN=<your bot token> python3 scripts/file-ids.py --prompt
```

It prints ready-made instructions with your bot's ids filled in, like this (ids shortened):

```text
Stickers you can send on Telegram (use the "sticker" action with the fileId):
- When you finished something you were asked to do, send sticker CAACAgIAAxUAAW... (🫡 done).
- When you need the owner's yes on something, send sticker CAACAgIAAxUAAW... (📡 copy).
...
```

Use `--json` instead for a `{"done": "<file_id>", ...}` map, or no flag for a plain list.
Without a set name it uses Speedy; pass a set name or a `t.me/addstickers/` link for any other
set.

**3. Give those lines to your agent**, for example in its workspace `AGENTS.md`. The agent then
sends a sticker with OpenCLAW's `sticker` action:

```json5
{ action: "sticker", channel: "telegram", to: "<chat id>", fileId: "<file_id from step 2>" }
```

OpenCLAW also has a `sticker-search` action, but it only finds stickers your bot has already
seen in a chat. With the ids from step 2 your agent does not need it.

## Any other bot

The same two Bot API calls work from anything that can make an HTTP request:
`getStickerSet` with `name=speedy_by_GodspeedStickersBot` returns every sticker with a `file_id` for the bot
that asked, and `sendSticker` with `chat_id` and that `file_id` sends it.
