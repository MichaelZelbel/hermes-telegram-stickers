# godspeed-stickers for Hermes Agent

Lets your Hermes agent send a Telegram sticker to the person it is talking to. The agent ends a
reply with a tag such as `[[sticker:done]]`; just before the reply goes out, the plugin sends the
matching sticker through your bot and removes the tag. The person sees Speedy saluting and the
words, never the tag.

It started as the plugin that sends Godspeed Mission Control's own "do you copy?" sticker, and
was made general so any Hermes gateway can use it.

## Install

You need a Hermes gateway that already talks to you on Telegram.

```sh
hermes plugins install MichaelZelbel/godspeed-stickers/hermes-plugin --enable
hermes gateway restart
```

Or by hand: copy this folder to `~/.hermes/plugins/godspeed-stickers`, then run
`hermes plugins enable godspeed-stickers` and `hermes gateway restart`. Hermes only loads plugins
you have enabled.

`hermes plugins list` should now show `godspeed-stickers` as enabled.

## Tell your agent when to send one

Add a line or two to your agent's instructions, for example in `~/.hermes/SOUL.md`:

> When you finish something I asked for, end your reply with `[[sticker:done]]`.
> When you need my yes on something, end it with `[[sticker:copy]]`.

All seven tags:

- `[[sticker:today]]` 🎧 here and listening
- `[[sticker:onit]]` 💻 on it
- `[[sticker:note]]` 📝 a note for you
- `[[sticker:copy]]` 📡 do you copy? I need your yes
- `[[sticker:fix]]` 🔧 fixing it
- `[[sticker:done]]` 🫡 done
- `[[sticker:quiet]]` 😴 keeping quiet watch

## What it does exactly

- It sends one sticker per reply: the first tag it knows. Every tag is removed, known or not.
- The sticker goes to the chat the reply goes to, silently (the words that follow make the
  sound). Outside a Telegram chat, for example in `hermes chat` on the command line, the tag is
  only removed.
- It finds the sticker through your own bot: the first time, it asks Telegram for the whole set
  with your bot's token and remembers the ids. Telegram gives every bot its own ids, so ids from
  someone else's bot would not work.
- It uses the `TELEGRAM_BOT_TOKEN` your Telegram gateway already has in `~/.hermes/.env`. If no
  chat is known, it falls back to `TELEGRAM_HOME_CHANNEL`, then to the first user in
  `TELEGRAM_ALLOWED_USERS`.
- If something is missing (no token, no chat, a set that does not exist), the reply still goes
  out without the tag, and the gateway log says in one sentence what to fix.
- With streaming switched on, the tag can show for a moment until Hermes replaces the message
  with the final text.

## Settings

All optional. Put them in `~/.hermes/.env` and restart the gateway.

- `GODSPEED_STICKER_SET`: a sticker set name, the part after `t.me/addstickers/`.
  Default: Speedy (`speedy_by_<BOT>`).
- `GODSPEED_STICKER_TAGS`: your own tags for your own set, as `tag=emoji` pairs:
  `GODSPEED_STICKER_TAGS=yay=🎉,hmm=🤔`. Each emoji must be the one Telegram shows for that
  sticker in the set. This replaces the Speedy tags.
- `GODSPEED_STICKER_PLATFORMS`: where a tag sends a sticker. Default `telegram`. Add `cron` if
  your scheduled jobs deliver to Telegram, or use `*` for everywhere.
- `GODSPEED_STICKER_CHAT`: always send stickers to this chat id.
- `GODSPEED_STICKER_API_BASE`: the Bot API address, if you run your own Bot API server.
  Default `https://api.telegram.org`.

## Tests

From the repository root: `python3 -m unittest discover -s tests -v`. Run with a Python that can
import Hermes, this also installs the plugin into a throwaway Hermes home and runs a real gateway
against a stand-in for Telegram on your machine. Nothing reaches Telegram.
