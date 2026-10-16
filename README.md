# Godspeed Stickers

Free Telegram stickers for AI agents, plus the small piece of software that lets your agent's
Telegram bot send one to you at the right moment: when it finished a job, when it needs your yes,
when it is fixing something.

<p>
<img src="packs/speedy/speedy-today.png" width="88" alt="Speedy with headphones">
<img src="packs/speedy/speedy-onit.png" width="88" alt="Speedy at a laptop">
<img src="packs/speedy/speedy-note.png" width="88" alt="Speedy with a note">
<img src="packs/speedy/speedy-copy.png" width="88" alt="Speedy on the radio">
<img src="packs/speedy/speedy-fix.png" width="88" alt="Speedy with a wrench">
<img src="packs/speedy/speedy-done.png" width="88" alt="Speedy saluting">
<img src="packs/speedy/speedy-quiet.png" width="88" alt="Speedy asleep">
</p>

## The stickers

**Speedy** is the little cloud ghost from [Godspeed Mission Control](https://godspeedmissioncontrol.com),
in seven poses. The word in front is the tag your agent uses.

- `today` 🎧 here and listening
- `onit` 💻 on it
- `note` 📝 a note for you
- `copy` 📡 do you copy? I need your yes
- `fix` 🔧 fixing it
- `done` 🫡 done
- `quiet` 😴 keeping quiet watch

Add them to your own Telegram: https://t.me/addstickers/speedy_by_GodspeedStickersBot
<!-- The set name above is filled in by scripts/publish-set.sh when the set is published. -->

## Let your bot send them

**Hermes Agent.** Install the plugin and restart the gateway:

```sh
hermes plugins install MichaelZelbel/godspeed-stickers/hermes-plugin --enable
hermes gateway restart
```

Then tell your agent when to use them, for example in `~/.hermes/SOUL.md`:

> When you finish something I asked for, end your reply with `[[sticker:done]]`.
> When you need my yes on something, end it with `[[sticker:copy]]`.

The plugin sends the sticker and removes the tag, so you only see Speedy and the words. More in
[hermes-plugin/README.md](hermes-plugin/README.md).

**OpenCLAW.** It can send stickers already. Switch the sticker action on, then get the stickers'
ids for your own bot and hand them to your agent:

```sh
git clone https://github.com/MichaelZelbel/godspeed-stickers && cd godspeed-stickers
BOT_TOKEN=<your bot token> python3 scripts/file-ids.py --prompt
```

Step by step in [INTEGRATIONS.md](INTEGRATIONS.md).

## Why your bot looks the stickers up itself

Telegram gives every bot its own id for the same sticker, and an id from one bot does not work
for another. So this repository does not ship ids. The Hermes plugin asks Telegram for them
through your bot the first time it needs one, and `scripts/file-ids.py` does the same for
OpenCLAW.

## Add your own pack

Put your PNGs and a `manifest.json` in `packs/<your-pack>/` and open a pull request. The details
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
repackage it, no credit needed. A link back to Godspeed Mission Control is always welcome.
