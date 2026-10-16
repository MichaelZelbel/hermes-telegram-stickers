#!/usr/bin/env bash
# Publish packs as Telegram sticker sets made by YOUR bot, then record them in the manifests.
#
#   BOT_TOKEN=<bot token> OWNER_USER_ID=<your Telegram user id> scripts/publish-set.sh <pack>...
#   BOT_TOKEN=<bot token> OWNER_USER_ID=<your Telegram user id> scripts/publish-set.sh --all
#
# Telegram names a set after the bot that makes it, so a set becomes
# <pack name>_by_<your bot's username>, e.g. speedy_by_MyStickerBot.
# OWNER_USER_ID is the Telegram account that will own the sets; send /start to the bot from that
# account once before running this, or Telegram refuses.
#
# - A set that does not exist yet is created with every sticker in its manifest.
# - A set that exists keeps its stickers: each gets the manifest's emoji list, the title follows
#   the manifest, and stickers the manifest has beyond the set's count are added at the end, in
#   order. If the set's stickers are not in the manifest's order, nothing is changed.
# Afterwards each manifest gets telegram_set_name and telegram_set, and the docs and the Hermes
# plugin name the new set wherever they named the old one (or the <pack>_by_<BOT> placeholder),
# so a fork published under its own bot links to its own sets.
#
# The token never appears in output or on the command line of any process it starts.
# TELEGRAM_API_BASE points it at another Bot API server (default https://api.telegram.org).
set -euo pipefail

if [ $# -eq 0 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then PY=python3; else PY=python; fi
PACKPY=("$PY" "$ROOT/scripts/pack.py")

PACKS=()
if [ "$1" = "--all" ]; then
  while IFS= read -r P; do PACKS+=("${P%$'\r'}"); done < <("${PACKPY[@]}" list)
else
  PACKS=("$@")
fi
for PACK in "${PACKS[@]}"; do
  [ -f "$ROOT/packs/$PACK/manifest.json" ] || { echo "No pack called '$PACK' (expected packs/$PACK/manifest.json)."; exit 1; }
done
: "${BOT_TOKEN:?Set BOT_TOKEN to the token of the bot that should own the sets (from @BotFather).}"
: "${OWNER_USER_ID:?Set OWNER_USER_ID to your own Telegram user id (that account will own the sets).}"
API="${TELEGRAM_API_BASE:-https://api.telegram.org}"
API="${API%/}"

echo "Checking the packs..."
if [ "$1" = "--all" ]; then
  "${PACKPY[@]}" check --all
else
  for PACK in "${PACKS[@]}"; do "${PACKPY[@]}" check "$PACK"; done
fi

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
ok() { [ "$(field "$1" ok)" = "True" ] || fail "$1"; }

# Text with emoji or accents goes to curl through files, so it arrives as UTF-8 on every system.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ME="$(tg getMe)"
ok "$ME"
BOT="$(field "$ME" result username)"

publish() {
  local PACK="$1" NAME COUNT EXISTING HAVE R KIND A B i ITEM CHECK
  NAME="$("${PACKPY[@]}" set-name "$PACK" "$BOT")"
  "${PACKPY[@]}" title "$PACK" | tr -d '\r\n' > "$WORK/title"
  COUNT="$("${PACKPY[@]}" count "$PACK")"
  local FILES=()
  while IFS= read -r F; do FILES+=("${F%$'\r'}"); done < <("${PACKPY[@]}" files "$PACK")
  echo
  echo "Bot: @$BOT   set: $NAME   stickers in pack: $COUNT"

  EXISTING="$(tg getStickerSet -d "name=$NAME")"
  if [ "$(field "$EXISTING" ok)" = "True" ]; then
    HAVE="$(field "$EXISTING" result stickers len)"
    echo "The set already exists with $HAVE sticker(s)."
    printf '%s' "$EXISTING" | "${PACKPY[@]}" plan "$PACK" | tr -d '\r' > "$WORK/plan"
    if grep -q '^mismatch' "$WORK/plan"; then
      while read -r KIND A B; do
        echo "  sticker $A in the set is not the manifest's '$B' sticker (different first emoji)"
      done < <(grep '^mismatch' "$WORK/plan")
      echo "Nothing changed. Put the manifest in the set's order, or fix the set by hand."
      exit 1
    fi
    while read -r KIND A B; do
      case "$KIND" in
        emoji)
          R="$(tg setStickerEmojiList --form-string "sticker=$A" --form-string "emoji_list=$B")"
          ok "$R" ;;
        title)
          R="$(tg setStickerSetTitle --form-string "name=$NAME" -F "title=<$WORK/title")"
          ok "$R"
          echo "  title updated" ;;
        extra)
          echo "  note: the set has $A sticker(s) the manifest does not list; they stay" ;;
      esac
    done < "$WORK/plan"
    echo "  emoji lists of the existing stickers match the manifest"
    if [ "$HAVE" -lt "$COUNT" ]; then
      i="$HAVE"
      while IFS= read -r ITEM; do
        ITEM="${ITEM%$'\r'}"
        ITEM="${ITEM//attach:\/\/s$i/attach://s0}"
        R="$(tg addStickerToSet --form-string "user_id=$OWNER_USER_ID" --form-string "name=$NAME" \
               --form-string "sticker=$ITEM" -F "s0=@${FILES[$i]}")"
        ok "$R"
        echo "  added $(basename "${FILES[$i]}")"
        i=$((i + 1))
      done < <("${PACKPY[@]}" input-stickers "$PACK" "$HAVE")
    fi
  else
    local ARGS=()
    for i in "${!FILES[@]}"; do ARGS+=(-F "s$i=@${FILES[$i]}"); done
    R="$(tg createNewStickerSet --form-string "user_id=$OWNER_USER_ID" --form-string "name=$NAME" \
           -F "title=<$WORK/title" --form-string "stickers=$("${PACKPY[@]}" input-stickers "$PACK")" \
           "${ARGS[@]}")"
    ok "$R"
    echo "Created the set with $COUNT sticker(s)."
  fi

  CHECK="$(tg getStickerSet -d "name=$NAME")"
  ok "$CHECK"
  echo "Telegram now lists $(field "$CHECK" result stickers len) sticker(s) in $NAME."
  "${PACKPY[@]}" record "$PACK" "$NAME"
  echo "https://t.me/addstickers/$NAME"
}

for PACK in "${PACKS[@]}"; do publish "$PACK"; done
echo
echo "Commit the updated files above."
