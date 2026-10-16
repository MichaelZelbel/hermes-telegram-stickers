# Adding a sticker pack

1. Pick a short name for your pack: lowercase letters, digits, `-` or `_`, starting with a
   letter. Make a folder for it: `packs/your-pack/`.
2. Add your images, one PNG per sticker, transparent background. Telegram's rules for static
   stickers: one side exactly 512 px, the other 512 px or less, at most 512 KB per file.
3. Add a `manifest.json` next to them:

   ```json
   {
     "name": "your-pack",
     "title": "What people see as the set's title",
     "telegram_set_name": null,
     "telegram_set": null,
     "stickers": [
       { "pose": "wave", "file": "wave.png", "emoji": ["👋"], "when": "you say hello" }
     ]
   }
   ```

   - `pose` is the word an agent uses to ask for this sticker, as in `[[sticker:wave]]`.
   - `emoji` is a list of 1 to 20 emoji. The first one must be different for every sticker in
     the pack, because that is how a bot finds the sticker in the set.
   - `when` is optional: the moment the sticker is for, in a few words. `scripts/file-ids.py
     --prompt` turns it into an instruction for the agent.
   - Leave `telegram_set_name` and `telegram_set` as `null`. Publishing fills them in.
   - No `file_id`. Every bot gets its own, so a stored one would only work for one bot.
4. Check it: `python3 scripts/pack.py check your-pack`
5. Open a pull request. We also look at whether everything in it is fine to make public: no real
   person's likeness without their OK, nothing that pretends to belong to a project, bot or
   brand it is not part of.

Once it is merged, we publish it as a Telegram set:

```sh
BOT_TOKEN=<bot token> OWNER_USER_ID=<owner's Telegram user id> scripts/publish-set.sh your-pack
```

That creates `your_pack_by_<bot username>` (or adds new stickers to the end of a set that
already exists) and writes the set's name and link into your manifest.

No sticker gets turned down for being simple. A clear sticker you can read at thumbnail size
beats an elaborate one nobody can make out in a chat.
