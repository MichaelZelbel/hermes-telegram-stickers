# Hermes Telegram Stickers

Free Telegram stickers for [Hermes Agent](https://github.com/NousResearch/hermes-agent), and a
plugin that lets your Hermes bot send one at the right moment: when it finished a job, when it
needs your yes, when it is fixing something.

Three sets with the same fifteen moments, so switching sets is one setting.

**Speedy**, a soft felt cloud ghost. Speedy is the mascot of
[Godspeed Mission Control](https://godspeedmissioncontrol.com), a personal AI that runs on
Hermes, so these stickers work there too.
Add them: https://t.me/addstickers/speedy_by_GodspeedStickersBot

<p>
<img src="packs/speedy/speedy-today.png" width="52" alt="Speedy: here and listening">
<img src="packs/speedy/speedy-onit.png" width="52" alt="Speedy: on it">
<img src="packs/speedy/speedy-note.png" width="52" alt="Speedy: a note for you">
<img src="packs/speedy/speedy-copy.png" width="52" alt="Speedy: do you copy? I need your yes">
<img src="packs/speedy/speedy-fix.png" width="52" alt="Speedy: fixing it">
<img src="packs/speedy/speedy-done.png" width="52" alt="Speedy: done">
<img src="packs/speedy/speedy-quiet.png" width="52" alt="Speedy: keeping quiet watch">
<img src="packs/speedy/speedy-ok.png" width="52" alt="Speedy: got it">
<img src="packs/speedy/speedy-think.png" width="52" alt="Speedy: thinking it over">
<img src="packs/speedy/speedy-found.png" width="52" alt="Speedy: found it">
<img src="packs/speedy/speedy-oops.png" width="52" alt="Speedy: my mistake">
<img src="packs/speedy/speedy-party.png" width="52" alt="Speedy: good news">
<img src="packs/speedy/speedy-thanks.png" width="52" alt="Speedy: thank you">
<img src="packs/speedy/speedy-morning.png" width="52" alt="Speedy: good morning">
<img src="packs/speedy/speedy-night.png" width="52" alt="Speedy: good night">
</p>

**Bit**, a pixel art robot.
Add them: https://t.me/addstickers/bit_by_<BOT>

<p>
<img src="packs/bit/bit-today.png" width="52" alt="Bit: here and listening">
<img src="packs/bit/bit-onit.png" width="52" alt="Bit: on it">
<img src="packs/bit/bit-note.png" width="52" alt="Bit: a note for you">
<img src="packs/bit/bit-copy.png" width="52" alt="Bit: do you copy? I need your yes">
<img src="packs/bit/bit-fix.png" width="52" alt="Bit: fixing it">
<img src="packs/bit/bit-done.png" width="52" alt="Bit: done">
<img src="packs/bit/bit-quiet.png" width="52" alt="Bit: keeping quiet watch">
<img src="packs/bit/bit-ok.png" width="52" alt="Bit: got it">
<img src="packs/bit/bit-think.png" width="52" alt="Bit: thinking it over">
<img src="packs/bit/bit-found.png" width="52" alt="Bit: found it">
<img src="packs/bit/bit-oops.png" width="52" alt="Bit: my mistake">
<img src="packs/bit/bit-party.png" width="52" alt="Bit: good news">
<img src="packs/bit/bit-thanks.png" width="52" alt="Bit: thank you">
<img src="packs/bit/bit-morning.png" width="52" alt="Bit: good morning">
<img src="packs/bit/bit-night.png" width="52" alt="Bit: good night">
</p>

**Mochi**, an ink doodle cat.
Add them: https://t.me/addstickers/mochi_by_<BOT>

<p>
<img src="packs/mochi/mochi-today.png" width="52" alt="Mochi: here and listening">
<img src="packs/mochi/mochi-onit.png" width="52" alt="Mochi: on it">
<img src="packs/mochi/mochi-note.png" width="52" alt="Mochi: a note for you">
<img src="packs/mochi/mochi-copy.png" width="52" alt="Mochi: do you copy? I need your yes">
<img src="packs/mochi/mochi-fix.png" width="52" alt="Mochi: fixing it">
<img src="packs/mochi/mochi-done.png" width="52" alt="Mochi: done">
<img src="packs/mochi/mochi-quiet.png" width="52" alt="Mochi: keeping quiet watch">
<img src="packs/mochi/mochi-ok.png" width="52" alt="Mochi: got it">
<img src="packs/mochi/mochi-think.png" width="52" alt="Mochi: thinking it over">
<img src="packs/mochi/mochi-found.png" width="52" alt="Mochi: found it">
<img src="packs/mochi/mochi-oops.png" width="52" alt="Mochi: my mistake">
<img src="packs/mochi/mochi-party.png" width="52" alt="Mochi: good news">
<img src="packs/mochi/mochi-thanks.png" width="52" alt="Mochi: thank you">
<img src="packs/mochi/mochi-morning.png" width="52" alt="Mochi: good morning">
<img src="packs/mochi/mochi-night.png" width="52" alt="Mochi: good night">
</p>

<!-- The bit and mochi set names above are filled in by scripts/publish-set.sh
     when the sets are published. -->

## Let your Hermes bot send them

Install the plugin and restart the gateway:

```sh
hermes plugins install MichaelZelbel/hermes-telegram-stickers/hermes-plugin --enable
hermes gateway restart
```

Then tell your agent when to use them, for example in `~/.hermes/SOUL.md`:

> When you finish something I asked for, end your reply with `[[sticker:done]]`.
> When you need my yes on something, end it with `[[sticker:copy]]`.

The plugin sends the sticker through your own bot and removes the tag, so you only see the
sticker and the words. To use Bit or Mochi instead of Speedy, put `STICKERS_SET=bit` or
`STICKERS_SET=mochi` in `~/.hermes/.env`. Settings and details:
[hermes-plugin/README.md](hermes-plugin/README.md).

## The tags

Every set has all fifteen. The word in front is what your agent writes, as in
`[[sticker:done]]`.

- `today` 🎧 here and listening
- `onit` 💻 on it
- `note` 📝 a note for you
- `copy` 📡 do you copy? I need your yes
- `fix` 🔧 fixing it
- `done` 🫡 done
- `quiet` 😴 keeping quiet watch
- `ok` 👍 got it
- `think` 🤔 thinking it over
- `found` 🔍 found it
- `oops` 😅 my mistake
- `party` 🎉 good news
- `thanks` 🙏 thank you
- `morning` ☕ good morning
- `night` 🌙 good night

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
