#!/usr/bin/env bash
# Publish a pack as a Telegram sticker set made by YOUR bot, then record it in the manifest.
#
#   BOT_TOKEN=<bot token> OWNER_USER_ID=<your Telegram user id> scripts/publish-set.sh <pack>
#
# Telegram names a set after the bot that makes it, so the set becomes
# <pack name>_by_<your bot's username>, e.g. speedy_by_MyStickerBot.
# OWNER_USER_ID is the Telegram account that will own the set; send /start to the bot from that
# account once before running this, or Telegram refuses.
#
# - If the set does not exist yet, it is created with every sticker in the manifest.
# - If it exists, stickers the manifest has beyond the set's count are added to the end.
# Afterwards packs/<pack>/manifest.json gets telegram_set_name and telegram_set, and the docs
# and the Hermes plugin name the new set wherever they named the old one (or the
# <pack>_by_<BOT> placeholder), so a fork published under its own bot links to its own set.
#
# The token never appears in output or on the command line of any process it starts.
# TELEGRAM_API_BASE points it at another Bot API server (default https://api.telegram.org).
set -euo pipefail

PACK="${1:-}"
if [ -z "$PACK" ] || [ "$PACK" = "-h" ] || [ "$PACK" = "--help" ]; then
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then PY=python3; else PY=python; fi
PACKPY=("$PY" "$ROOT/scripts/pack.py")
[ -f "$ROOT/packs/$PACK/manifest.json" ] || { echo "No pack called '$PACK' (expected packs/$PACK/manifest.json)."; exit 1; }
: "${BOT_TOKEN:?Set BOT_TOKEN to the token of the bot that should own the set (from @BotFather).}"
: "${OWNER_USER_ID:?Set OWNER_USER_ID to your own Telegram user id (that account will own the set).}"
API="${TELEGRAM_API_BASE:-https://api.telegram.org}"
API="${API%/}"

echo "Checking the pack..."
"${PACKPY[@]}" check "$PACK"

# tg <method> [curl args...]: call the Bot API. The URL (which holds the token) goes to curl
# through its config on stdin, so it never shows up in a process list or in any output.
tg() {
  local method="$1"; shift
  printf 'url = "%s/bot%s/%s"\n' "$API" "$BOT_TOKEN" "$method" | curl -sS -K - "$@"
}
# field <json> <key...>: one value out of a JSON answer (empty if missing); a last key "len"
# gives a list's length. The JSON goes in on stdin as UTF-8, never as an argument.
field() {
  local json="$1"; shift
  printf '%s' "$json" | "$PY" -c 'import json, sys
try:
    d = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
except ValueError:
    d = {"description": "an answer that is not JSON"}
for k in sys.argv[1:]:
    if k == "len":
        d = len(d) if isinstance(d, list) else 0
    else:
        d = d.get(k) if isinstance(d, dict) else None
sys.stdout.buffer.write(("" if d is None else str(d)).encode("utf-8"))' "$@"
}
fail() { echo "Telegram refused: $(field "$1" description)"; exit 1; }

# Text with emoji or accents goes to curl through files, so it arrives as UTF-8 on every system.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ME="$(tg getMe)"
[ "$(field "$ME" ok)" = "True" ] || fail "$ME"
BOT="$(field "$ME" result username)"
NAME="$("${PACKPY[@]}" set-name "$PACK" "$BOT")"
"${PACKPY[@]}" title "$PACK" | tr -d '\r\n' > "$WORK/title"
COUNT="$("${PACKPY[@]}" count "$PACK")"
FILES=()
while IFS= read -r F; do FILES+=("${F%$'\r'}"); done < <("${PACKPY[@]}" files "$PACK")
echo "Bot: @$BOT   set: $NAME   stickers in pack: $COUNT"

EXISTING="$(tg getStickerSet -d "name=$NAME")"
if [ "$(field "$EXISTING" ok)" = "True" ]; then
  HAVE="$(field "$EXISTING" result stickers len)"
  echo "The set already exists with $HAVE sticker(s)."
  if [ "$HAVE" -lt "$COUNT" ]; then
    i="$HAVE"
    while IFS= read -r ITEM; do
      ITEM="${ITEM%$'\r'}"
      ITEM="${ITEM//attach:\/\/s$i/attach://s0}"
      R="$(tg addStickerToSet --form-string "user_id=$OWNER_USER_ID" --form-string "name=$NAME" \
             --form-string "sticker=$ITEM" -F "s0=@${FILES[$i]}")"
      [ "$(field "$R" ok)" = "True" ] || fail "$R"
      echo "  added $(basename "${FILES[$i]}")"
      i=$((i + 1))
    done < <("${PACKPY[@]}" input-stickers "$PACK" "$HAVE")
  fi
else
  ARGS=()
  for i in "${!FILES[@]}"; do ARGS+=(-F "s$i=@${FILES[$i]}"); done
  R="$(tg createNewStickerSet --form-string "user_id=$OWNER_USER_ID" --form-string "name=$NAME" \
         -F "title=<$WORK/title" --form-string "stickers=$("${PACKPY[@]}" input-stickers "$PACK")" \
         "${ARGS[@]}")"
  [ "$(field "$R" ok)" = "True" ] || fail "$R"
  echo "Created the set with $COUNT sticker(s)."
fi

CHECK="$(tg getStickerSet -d "name=$NAME")"
[ "$(field "$CHECK" ok)" = "True" ] || fail "$CHECK"
echo "Telegram now lists $(field "$CHECK" result stickers len) sticker(s) in $NAME."

"${PACKPY[@]}" record "$PACK" "$NAME"
echo
echo "https://t.me/addstickers/$NAME"
echo "Commit the updated files above."
