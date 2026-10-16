# hermes-telegram-stickers, the Hermes plugin

Lets your Hermes agent send a Telegram sticker to the person it is talking to. The agent ends a
reply with a tag such as `[[sticker:done]]`; just before the reply goes out, the plugin sends the
matching sticker through your bot and removes the tag. The person sees the sticker and the
words, never the tag.

## Install

You need a Hermes gateway that already talks to you on Telegram.

```sh
hermes plugins install MichaelZelbel/hermes-telegram-stickers/hermes-plugin --enable
hermes gateway restart
```

Or by hand: copy this folder to `~/.hermes/plugins/hermes-telegram-stickers`, then run
`hermes plugins enable hermes-telegram-stickers` and `hermes gateway restart`. Hermes only loads
plugins you have enabled.

`hermes plugins list` should now show `hermes-telegram-stickers` as enabled.

## Tell your agent when to send one

Add a line or two to your agent's instructions, for example in `~/.hermes/SOUL.md`:

> When you finish something I asked for, end your reply with `[[sticker:done]]`.
> When you need my yes on something, end it with `[[sticker:copy]]`.

Every tag and what it means is listed in the [main README](../README.md#the-tags).

## What it does exactly

- It sends one sticker per reply: the first tag it knows. Every tag is removed, known or not.
- The sticker goes to the chat the reply goes to, silently (the words that follow make the
  sound). Outside a Telegram chat, for example in `hermes chat` on the command line, the tag is
  only removed.
- It finds the sticker through your own bot: the first time, it asks Telegram for the whole set
  with your bot's token and remembers the ids. Telegram gives every bot its own ids, so ids from
  someone else's bot would not work.
- It matches a tag to the sticker whose first emoji is that tag's emoji, and to nothing else. If
  two stickers in a set have the same first emoji, it sends neither.
- It uses the `TELEGRAM_BOT_TOKEN` your Telegram gateway already has in `~/.hermes/.env`. If no
  chat is known, it falls back to `TELEGRAM_HOME_CHANNEL`, then to the first user in
  `TELEGRAM_ALLOWED_USERS`.
- If something is missing (no token, no chat, a set that does not exist), the reply still goes
  out without the tag, and the gateway log says in one sentence what to fix.
- With streaming switched on, the tag can show for a moment until Hermes replaces the message
  with the final text.

## Settings

All optional. Put them in `~/.hermes/.env` and restart the gateway.

- `STICKERS_SET`: which stickers to send. `speedy` (the default), `bit`, `mochi`, or the name of
  any Telegram sticker set, the part after `t.me/addstickers/`.
- `STICKERS_TAGS`: your own tags for your own set, as `tag=emoji` pairs:
  `STICKERS_TAGS=yay=🎉,hmm=🤔`. Each emoji must be the first emoji of that sticker in the set.
  This replaces the built-in tags.
- `STICKERS_PLATFORMS`: where a tag sends a sticker. Default `telegram`. Add `cron` if your
  scheduled jobs deliver to Telegram, or use `*` for everywhere.
- `STICKERS_CHAT`: always send stickers to this chat id.
- `STICKERS_API_BASE`: the Bot API address, if you run your own Bot API server. Default
  `https://api.telegram.org`.

## Tests

From the repository root: `python3 -m unittest discover -s tests -v`. Run with a Python that can
import Hermes, this also installs the plugin into a throwaway Hermes home and runs a real gateway
against a stand-in for Telegram on your machine. Nothing reaches Telegram.
