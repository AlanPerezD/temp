#!/usr/bin/env python3
"""Pre-flight check for the dedicated sending PC. Changes nothing, sends nothing.

    cd agencia-web-peru/leads
    python3 doctor.py                    # checks tools, bridge, DB, batch; prints the next command to run
    python3 doctor.py --bridge-dir ../../whatsapp-mcp/whatsapp-bridge --batch data/outreach_batch1.csv
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


def parse_go_version(text):
    m = re.search(r"go(\d+)\.(\d+)", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def bridge_up(url="http://localhost:8080"):
    """Any HTTP answer (even 404/405) means the bridge's REST server is running."""
    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def summarize_batch(rows):
    n = len(rows)
    count = lambda col: sum(1 for r in rows if (r.get(col) or "").strip())
    return {
        "rows": n, "sent": count("sent"), "replied": count("replied"), "stop": count("stop"),
        "opt_in": count("opt_in"), "pending": sum(1 for r in rows if not (r.get("sent") or "").strip()
                                                  and not (r.get("stop") or "").strip()),
        "has_followup_text": count("followup"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bridge-dir", default="../../whatsapp-mcp/whatsapp-bridge")
    ap.add_argument("--bridge-url", default="http://localhost:8080")
    ap.add_argument("--batch", default="data/outreach_batch1.csv")
    args = ap.parse_args(argv)

    problems, notes = [], []

    def check(ok, good, bad, fix):
        print(("  OK   " if ok else "  FALTA ") + (good if ok else bad))
        if not ok:
            problems.append(fix)

    print("Herramientas")
    check(sys.version_info >= (3, 9), f"Python {sys.version.split()[0]}", "Python 3.9+ requerido", "Instala Python 3.9 o superior")
    check(bool(shutil.which("git")), "git", "git no encontrado", "Instala git")
    go = parse_go_version(run(["go", "version"])) if shutil.which("go") else None
    check(bool(go and go >= (1, 21)), f"Go {go[0]}.{go[1]}" if go else "Go", "Go 1.21+ no encontrado",
          "Instala Go 1.21+ (https://go.dev/dl/)")
    if os.name == "nt":
        check(bool(shutil.which("gcc")), "compilador C (gcc)", "gcc no encontrado (el puente lo necesita en Windows)",
              "Instala MSYS2, añade ucrt64\\bin al PATH y ejecuta: go env -w CGO_ENABLED=1")

    print("Puente de WhatsApp")
    has_dir = os.path.isdir(args.bridge_dir)
    check(has_dir, f"carpeta {args.bridge_dir}", f"no existe {args.bridge_dir}", "Ejecuta setup_pc.sh / setup_pc.ps1")
    store = os.path.join(args.bridge_dir, "store")
    has_db = os.path.exists(os.path.join(store, "whatsapp.db"))
    check(has_db, "sesión vinculada (store/whatsapp.db)", "aún no has escaneado el QR",
          f"En otra terminal: cd {args.bridge_dir} && go run main.go y escanea el QR con el número secundario")
    check(bridge_up(args.bridge_url), f"el puente responde en {args.bridge_url}", f"el puente no responde en {args.bridge_url}",
          "Deja corriendo el puente (go run main.go) en una terminal aparte")

    print("Lote")
    if os.path.exists(args.batch):
        with open(args.batch, newline="", encoding="utf-8-sig") as f:
            s = summarize_batch(list(csv.DictReader(f)))
        check(s["rows"] > 0, f"{args.batch}: {s['rows']} filas, {s['pending']} pendientes, {s['sent']} enviados, "
                             f"{s['replied']} respuestas, {s['stop']} stop", "lote vacío", "Genera el lote: python3 make_outreach.py")
        if s["opt_in"] == 0:
            notes.append("La columna opt_in está vacía: con --require-opt-in el envío programado no contactará a nadie. "
                         "Rellénala solo para quien pidió que le escribas (respondió, anuncio, formulario).")
    else:
        check(False, "", f"no existe {args.batch}", "Copia data/ del repo privado a agencia-web-peru/leads/data/")
    check(not os.path.exists("STOP"), "sin archivo STOP", "hay un archivo STOP (el envío está detenido)", "Borra STOP para reanudar")

    print()
    for n in notes:
        print("NOTA:", n)
    if problems:
        print("\nPendiente:")
        for i, p in enumerate(dict.fromkeys(problems), 1):
            print(f" {i}. {p}")
        return 1
    print("Todo listo. Prueba a tu número (no envía nada sin --live):")
    print("  python3 scheduled_sender.py --test-to <TU_NUMERO_CON_CODIGO_PAIS>")
    print("  python3 scheduled_sender.py --test-to <TU_NUMERO_CON_CODIGO_PAIS> --live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
