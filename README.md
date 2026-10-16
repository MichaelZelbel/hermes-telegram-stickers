# Hermes Telegram Stickers

Free Telegram stickers for [Hermes Agent](https://github.com/NousResearch/hermes-agent), and a
plugin that lets your Hermes bot send one at the right moment: when it finished a job, when it
needs your yes, when it is fixing something.

<p>
<img src="packs/speedy/speedy-today.png" width="88" alt="Speedy with headphones">
<img src="packs/speedy/speedy-onit.png" width="88" alt="Speedy at a laptop">
<img src="packs/speedy/speedy-note.png" width="88" alt="Speedy with a note">
<img src="packs/speedy/speedy-copy.png" width="88" alt="Speedy on the radio">
<img src="packs/speedy/speedy-fix.png" width="88" alt="Speedy with a wrench">
<img src="packs/speedy/speedy-done.png" width="88" alt="Speedy saluting">
<img src="packs/speedy/speedy-quiet.png" width="88" alt="Speedy asleep">
</p>

**Speedy** is the felt cloud ghost of [Godspeed Mission Control](https://godspeedmissioncontrol.com),
a personal AI that runs on Hermes, so these stickers work there too.

Add them to your own Telegram: https://t.me/addstickers/speedy_by_GodspeedStickersBot

## Let your Hermes bot send them

Install the plugin and restart the gateway:

```sh
hermes plugins install MichaelZelbel/hermes-telegram-stickers/hermes-plugin --enable
hermes gateway restart
```

Then tell your agent when to use them, for example in `~/.hermes/SOUL.md`:

> When you finish something I asked for, end your reply with `[[sticker:done]]`.
> When you need my yes on something, end it with `[[sticker:copy]]`.

The plugin sends the sticker through your own bot and removes the tag, so you only see Speedy
and the words. Settings and details: [hermes-plugin/README.md](hermes-plugin/README.md).

## The tags

- `today` 🎧 here and listening
- `onit` 💻 on it
- `note` 📝 a note for you
- `copy` 📡 do you copy? I need your yes
- `fix` 🔧 fixing it
- `done` 🫡 done
- `quiet` 😴 keeping quiet watch

## Why your bot looks the stickers up itself

Telegram gives every bot its own id for the same sticker, and an id from one bot does not work
for another. So this repository ships no ids: the plugin asks Telegram for the set through your
bot the first time it needs a sticker, and finds each sticker by its first emoji.
`scripts/file-ids.py` does the same lookup by hand.

## Add your own set

Put your PNGs and a `manifest.json` in `packs/<your-set>/` and open a pull request. The details
are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Run the tests

```sh
python3 -m unittest discover -s tests -v
```

They never reach Telegram: a small stand-in for the Bot API runs on your machine. Run them with a
Python that can import Hermes and they also install the plugin into a throwaway Hermes home and
run a real Hermes gateway against that stand-in.

## License

Everything here, the artwork included, is [CC0](LICENSE): public domain. Use it, change it,
repackage it, no credit needed.

This is a community project. It is not made by or affiliated with Nous Research, the makers of
Hermes Agent.
