#!/usr/bin/env bash
# Prepara el PC de envíos (Mac/Linux). No envía nada y no arranca el puente (necesita tu QR).
#   bash setup_pc.sh [carpeta_de_trabajo]        # por defecto: ~/agencia
# Antes: `gh auth login` o tener acceso git al repo privado de datos (agencia-web-peru-leads).
set -euo pipefail

WORK="${1:-$HOME/agencia}"
mkdir -p "$WORK" && cd "$WORK"
missing=0
need() { command -v "$1" >/dev/null 2>&1 || { echo "FALTA $1: $2"; missing=1; }; }
need git "instálalo (https://git-scm.com)"
need python3 "instala Python 3.9+"
need go "instala Go 1.21+ (https://go.dev/dl/)"
need gcc "instala un compilador C (Mac: xcode-select --install · Linux: build-essential)"
[ "$missing" = 0 ] || { echo "Instala lo que falta y vuelve a ejecutar."; exit 1; }

clone() { [ -d "$2/.git" ] && echo "ya existe $2" || git clone "$1" "$2"; }
clone https://github.com/AlanPerezD/temp.git temp
git -C temp checkout ccr-bbdd28b9-1au9g8
clone https://github.com/AlanPerezD/agencia-web-peru-leads.git agencia-web-peru-leads
clone https://github.com/lharries/whatsapp-mcp.git whatsapp-mcp

# Los datos viven solo en el repo privado; se copian (no se commitean en temp).
DEST="temp/agencia-web-peru/leads/data"
mkdir -p "$DEST"
cp -n agencia-web-peru-leads/data/* "$DEST"/ 2>/dev/null || true

# Fija la versión del puente: si cambia sin que lo decidas, el script se detiene.
HEAD_NOW="$(git -C whatsapp-mcp rev-parse HEAD)"
if [ -f whatsapp-mcp.pin ] && [ "$(cat whatsapp-mcp.pin)" != "$HEAD_NOW" ]; then
  echo "AVISO: whatsapp-mcp cambió ($(cat whatsapp-mcp.pin | cut -c1-7) -> ${HEAD_NOW:0:7}). Revisa el código y borra whatsapp-mcp.pin para aceptar."
  exit 1
fi
echo "$HEAD_NOW" > whatsapp-mcp.pin
echo "whatsapp-mcp fijado en ${HEAD_NOW:0:7}. Revisa whatsapp-bridge/main.go y whatsapp-mcp-server/main.py antes de ejecutarlo."

cat <<EOF

Siguientes pasos (en $WORK):
 1) Terminal A (déjala abierta):  cd whatsapp-mcp/whatsapp-bridge && go run main.go
    -> escanea el QR con el NÚMERO SECUNDARIO (WhatsApp > Dispositivos vinculados).
 2) Terminal B:  cd temp/agencia-web-peru/leads && python3 doctor.py
 3) Prueba a TU número personal (no envía nada sin --live):
      python3 scheduled_sender.py --test-to <TU_NUMERO_CON_CODIGO_PAIS>
      python3 scheduled_sender.py --test-to <TU_NUMERO_CON_CODIGO_PAIS> --live
EOF
