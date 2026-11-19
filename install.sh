#!/usr/bin/env bash
# ============================================================
#   ARASAKA SHARD // instalador (Zorin OS / Ubuntu / Debian)
#   Cofre de senhas, chaves e codigos do autenticador
#
#   Uso:  ./install.sh [-y]        (NAO rode com sudo)
# ============================================================
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID=arasaka-shard
DATA="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_ID"
BIN="$HOME/.local/bin"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
YES=0
for a in "$@"; do
  case "$a" in
    -y|--yes) YES=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Opcao desconhecida: $a"; exit 1 ;;
  esac
done

R=$'\e[38;2;227;18;31m'; RH=$'\e[38;2;255;59;71m'; W=$'\e[38;2;236;236;240m'; G=$'\e[38;2;120;120;130m'; B=$'\e[1m'; N=$'\e[0m'
STEP=0
step() { STEP=$((STEP + 1)); printf '\n%s%s[%02d]%s %s%s%s\n' "$R" "$B" "$STEP" "$N" "$W$B" "$*" "$N"; }
ok()   { printf '     %s■%s %s\n' "$R" "$N" "$*"; }
info() { printf '     %s›%s %s\n' "$R" "$N" "$*"; }
warn() { printf '     %s!! %s%s\n' "$RH" "$*" "$N"; }
die()  { printf '\n%s!! %s%s\n' "$RH" "$*" "$N"; exit 1; }

printf '\n%s%s   A R A S A K A   S H A R D%s\n' "$R" "$B" "$N"
printf '   %sCofre de senhas%s\n' "$G" "$N"

[ "$EUID" -eq 0 ] && die "Rode como seu usuario normal (sem sudo): ./install.sh"
[ -f "$DIR/arasaka_shard/app.py" ] || die "Arquivos do app nao encontrados em $DIR"
command -v python3 >/dev/null || die "python3 nao encontrado"

if [ "$YES" -eq 0 ]; then
  printf '\n   Vai instalar o app (Python + Qt + libsodium).\n   %sContinuar? [s/N] %s' "$W" "$N"
  read -r r
  case "$r" in s|S|y|Y|sim|SIM) ;; *) echo "Cancelado."; exit 0 ;; esac
fi

step "Pacotes do sistema"
PKGS=(python3-venv python3-pip libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-image0
      libxcb-render-util0 libxcb-xinerama0 libxcb-shape0 libegl1 libnotify-bin)
MISSING=()
for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
if [ ${#MISSING[@]} -gt 0 ]; then
  info "instalando: ${MISSING[*]}"
  sudo apt-get update -qq || warn "apt update falhou"
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${MISSING[@]}" || warn "alguns pacotes falharam"
fi

step "Ambiente Python (PySide6 / Qt 6)"
mkdir -p "$DATA"
[ -x "$DATA/venv/bin/python" ] || python3 -m venv "$DATA/venv" || die "falha ao criar o venv (falta python3-venv?)"
"$DATA/venv/bin/python" -m pip install -q --upgrade pip >/dev/null 2>&1
info "baixando PySide6 (~120 MB na primeira vez)..."
"$DATA/venv/bin/python" -m pip install -q --upgrade "PySide6-Essentials>=6.5" "pynacl>=1.5" || die "falha ao instalar PySide6 e PyNaCl"
ok "PySide6 $("$DATA/venv/bin/python" -c 'import PySide6; print(PySide6.__version__)')"

step "Arquivos do app"
rm -rf "$DATA/app"
mkdir -p "$DATA/app" "$BIN" "$APPS" "$ICONS"
cp -r "$DIR/arasaka_shard" "$DATA/app/"
find "$DATA/app" -name '__pycache__' -prune -exec rm -rf {} +
cat > "$BIN/$APP_ID" <<EOS
#!/bin/sh
# ARASAKA SHARD launcher
export PYTHONPATH="$DATA/app\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$DATA/venv/bin/python" -m arasaka_shard "\$@"
EOS
chmod +x "$BIN/$APP_ID"
cp "$DIR/arasaka_shard/assets/$APP_ID.svg" "$ICONS/$APP_ID.svg"
# o tema de icones Arasaka tem um icone "arasaka": uma camada na pasta pessoal evita que ele substitua este
for th in /usr/share/icons/Arasaka "$HOME/.icons/Arasaka"; do
  if [ -f "$th/index.theme" ]; then
    UT="${XDG_DATA_HOME:-$HOME/.local/share}/icons/Arasaka"
    mkdir -p "$UT/scalable/apps"
    [ -f "$UT/index.theme" ] || cp "$th/index.theme" "$UT/index.theme"
    cp "$DIR/arasaka_shard/assets/$APP_ID.svg" "$UT/scalable/apps/$APP_ID.svg"
    break
  fi
done
cat > "$APPS/$APP_ID.desktop" <<EOS
[Desktop Entry]
Type=Application
Name=Arasaka Shard
GenericName=Cofre de senhas
Comment=Senhas, chaves e codigos do autenticador cifrados no seu PC
Exec="$BIN/$APP_ID"
Icon=$APP_ID
Terminal=false
Categories=Utility;Security;
Keywords=senha;password;cofre;2fa;totp;autenticador;arasaka;shard;
StartupWMClass=$APP_ID
EOS
update-desktop-database -q "$APPS" 2>/dev/null
gtk-update-icon-cache -q -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null
ok "atalho no menu: Arasaka Shard"


printf '\n%s%s ■ INSTALACAO CONCLUIDA%s\n' "$R" "$B" "$N"
printf '   %sAbra "Arasaka Shard" no menu (ou rode: arasaka-shard).%s\n\n' "$W" "$N"
