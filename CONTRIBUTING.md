# Adding a sticker set

Every set here has the same tags, so a Hermes user switches sets with one setting. A new set
draws the same moments in its own style.

1. Pick a short name for your set: lowercase letters, digits, `-` or `_`, starting with a letter.
   Make a folder for it: `packs/your-set/`.
2. Draw one sticker per tag (`python3 scripts/pack.py tags` lists them with their emoji). One
   PNG per sticker, transparent background. Telegram's rules for static stickers: one side
   exactly 512 px, the other 512 px or less, at most 512 KB per file.
3. Add a `manifest.json` next to them:

   ```json
   {
     "name": "your-set",
     "title": "What people see as the set's title",
     "telegram_set_name": null,
     "telegram_set": null,
     "stickers": [
       { "pose": "today", "file": "your-set-today.png", "emoji": ["🎧", "👋"] }
     ]
   }
   ```

   - `pose` is the tag, as in `[[sticker:today]]`. List the stickers in the order
     `pack.py tags` prints.
   - `emoji` is a list of 1 to 20 emoji. The first one must be the tag's emoji, because that is
     how the plugin finds the sticker. Each emoji may belong to only one sticker in the set.
   - Leave `telegram_set_name` and `telegram_set` as `null`. Publishing fills them in.
   - No `file_id`. Every bot gets its own, so a stored one would only work for one bot.
4. Check it: `python3 scripts/pack.py check --all`
5. Open a pull request. We also look at whether everything in it is fine to make public: no real
   person's likeness without their OK, nothing that pretends to belong to a project, bot or
   brand it is not part of.

Once it is merged, we publish it as a Telegram set:

```sh
BOT_TOKEN=<bot token> OWNER_USER_ID=<owner's Telegram user id> scripts/publish-set.sh your-set
```

That creates `your_set_by_<bot username>` and writes the set's name and link into your manifest.
Run against a set that already exists, it adds the manifest's new stickers to the end and gives
every sticker the manifest's emoji. `--all` publishes every set.

If you fork this repository and publish the sets under your own bot, the same command points
every link and the plugin's defaults at your sets.

No sticker gets turned down for being simple. A clear sticker you can read at thumbnail size
beats an elaborate one nobody can make out in a chat.
