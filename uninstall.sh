#!/usr/bin/env bash
# ARASAKA SHARD // desinstalador. O COFRE NAO E APAGADO (~/.config/arasaka-shard/cofre.shard).
set -uo pipefail
APP_ID=arasaka-shard
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
rm -f "$HOME/.local/bin/$APP_ID" "$APPS/$APP_ID.desktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps/$APP_ID.svg" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/icons/Arasaka/scalable/apps/$APP_ID.svg"
rm -rf "$DATA/app" "$DATA/venv"
update-desktop-database -q "$APPS" 2>/dev/null
echo "■ Arasaka Shard removido. O seu cofre continua em ~/.config/$APP_ID (cifrado); instale de novo para abrir."
