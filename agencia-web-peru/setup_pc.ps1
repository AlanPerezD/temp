# Prepara el PC de envíos (Windows, PowerShell). No envía nada y no arranca el puente (necesita tu QR).
#   powershell -ExecutionPolicy Bypass -File setup_pc.ps1 [-Work C:\agencia]
# Antes: tener acceso git al repo privado de datos (p. ej. `gh auth login` o Git Credential Manager).
# NOTA: este script no se pudo probar en Windows desde la nube; si algo falla, mándame el mensaje exacto.
param([string]$Work = "$HOME\agencia")
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Work | Out-Null
Set-Location $Work

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "FALTA ${cmd}: $hint"; $script:missing = $true }
}
$missing = $false
Need git    "winget install Git.Git"
Need python "winget install Python.Python.3.12"
Need go     "winget install GoLang.Go"
Need gcc    "winget install MSYS2.MSYS2; luego en la terminal MSYS2 UCRT64: pacman -S mingw-w64-ucrt-x86_64-gcc; y añade C:\msys64\ucrt64\bin al PATH"
if ($missing) { Write-Host "Instala lo que falta, abre una terminal NUEVA y vuelve a ejecutar."; exit 1 }
go env -w CGO_ENABLED=1

function CloneIf($url, $dir) { if (Test-Path "$dir\.git") { Write-Host "ya existe $dir" } else { git clone $url $dir } }
CloneIf "https://github.com/AlanPerezD/temp.git" "temp"
git -C temp checkout ccr-bbdd28b9-1au9g8
CloneIf "https://github.com/AlanPerezD/agencia-web-peru-leads.git" "agencia-web-peru-leads"
CloneIf "https://github.com/lharries/whatsapp-mcp.git" "whatsapp-mcp"

$dest = "temp\agencia-web-peru\leads\data"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item "agencia-web-peru-leads\data\*" $dest -Recurse -ErrorAction SilentlyContinue   # sin sobrescribir lo que ya editaste: cópialo a mano si hace falta

$headNow = (git -C whatsapp-mcp rev-parse HEAD).Trim()
if ((Test-Path "whatsapp-mcp.pin") -and ((Get-Content "whatsapp-mcp.pin").Trim() -ne $headNow)) {
  Write-Host "AVISO: whatsapp-mcp cambió. Revisa el código y borra whatsapp-mcp.pin para aceptar."; exit 1
}
Set-Content "whatsapp-mcp.pin" $headNow
Write-Host "whatsapp-mcp fijado en $($headNow.Substring(0,7)). Revisa whatsapp-bridge\main.go y whatsapp-mcp-server\main.py antes de ejecutarlo."

@"

Siguientes pasos (en $Work):
 1) Terminal A (déjala abierta):  cd whatsapp-mcp\whatsapp-bridge ; go run main.go
    -> escanea el QR con el NÚMERO SECUNDARIO (WhatsApp > Dispositivos vinculados).
 2) Terminal B:  cd temp\agencia-web-peru\leads ; python doctor.py --bridge-dir ..\..\..\whatsapp-mcp\whatsapp-bridge
 3) Prueba a TU número personal (no envía nada sin --live):
      python scheduled_sender.py --test-to <TU_NUMERO_CON_CODIGO_PAIS>
      python scheduled_sender.py --test-to <TU_NUMERO_CON_CODIGO_PAIS> --live
"@ | Write-Host
