# EPM – Images auf dem PC bauen und für die Übertragung speichern
# Aufruf in PowerShell im Ordner mit diesem Skript:   .\bauen.ps1            (Version aus der Datei VERSION)
#                                                      .\bauen.ps1 0.2.1      (andere Version)
param([string]$Version = "")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Ohne Angabe gilt die Version des Projekts - sonst entstuende ein Paket mit einer alten Nummer, das beim
# Einspielen eine neuere Fassung ueberschreibt (Stolperstein 06.10.2026).
if (-not $Version) { $Version = (Get-Content "VERSION" -Raw).Trim() }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Version nicht erkannt: '$Version' (erwartet X.Y.Z)." }

function Docker-Befehl {
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "Fehlgeschlagen: docker $($args -join ' ')" }
}

docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop läuft nicht - bitte starten und warten, bis 'Engine running' angezeigt wird." }

$Image = "epm-backend:$Version"
Write-Host "==> Baue $Image"
Docker-Befehl build -t $Image .\backend

if (-not (Test-Path .\backend\patienten\migrations\0001_initial.py)) {
    Write-Host "==> Erzeuge die Datenbank-Migrationen (nur beim ersten Mal)"
    Docker-Befehl run --rm -e DJANGO_DEBUG=1 -v "${PWD}\backend:/app" $Image `
        python manage.py makemigrations accounts stammdaten patienten infusionen audit
    Write-Host "==> Baue erneut, jetzt mit Migrationen"
    Docker-Befehl build -t $Image .\backend
}

Write-Host "==> Prüfe Projekt und Migrationen"
Docker-Befehl run --rm -e DJANGO_DEBUG=1 $Image python manage.py check
Docker-Befehl run --rm -e DJANGO_DEBUG=1 $Image python manage.py makemigrations --check --dry-run

Write-Host "==> Baue epm-web:$Version (Frontend)"
Docker-Befehl build -t "epm-web:$Version" .\frontend

Write-Host "==> Speichere beide Images"
Docker-Befehl save $Image "epm-web:$Version" -o "epm-$Version.tar"
Write-Host ""
Write-Host "Fertig. Weiter mit:"
Write-Host "   scp epm-$Version.tar epm-test:~"
