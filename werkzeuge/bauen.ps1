# EPM – Images auf dem PC bauen und für die Übertragung speichern
# Aufruf in PowerShell im Ordner mit diesem Skript:   .\bauen.ps1            (Version 0.1.0)
#                                                      .\bauen.ps1 0.1.1      (andere Version)
param([string]$Version = "0.1.0")
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

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

Write-Host "==> Speichere $Image"
Docker-Befehl save $Image -o "epm-backend-$Version.tar"
Write-Host ""
Write-Host "Fertig. Weiter mit:"
Write-Host "   scp epm-backend-$Version.tar epm-test:~"
