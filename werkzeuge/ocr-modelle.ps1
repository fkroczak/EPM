# EPM - Modelle der zweiten Texterkennung (PP-OCRv5, UVDoc) und das Sprachmodell fuer Diktate auf einem Windows-PC offline vorbereiten
# Gegenstueck zu werkzeuge/ocr-modelle.sh vorbereiten (fuer Linux, macOS, WSL).
#
# Aufruf in PowerShell im Ordner mit diesem Skript:   .\ocr-modelle.ps1
# Ergebnis: epm-ocr-modelle-<Revision>.tar im aktuellen Ordner (ca. 680 MB mit dem Sprachmodell fuer Diktate), geprueft gegen die Pruefsummen in
# backend\scans\modelle\modelle.json. Danach:
#   scp .\epm-ocr-modelle-<Revision>.tar epmadmin@TEST-VM:~/
#   auf der Test-VM:  sudo epm-ocr-modelle einspielen ~/epm-ocr-modelle-<Revision>.tar
#                     sudo epm-update
param([string]$Ziel = "")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # sonst ist Invoke-WebRequest in Windows PowerShell 5.1 sehr langsam
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Liste = Join-Path $PSScriptRoot "..\backend\scans\modelle\modelle.json"
if (-not (Test-Path $Liste)) { throw "Nicht gefunden: $Liste" }
$Daten = Get-Content $Liste -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Daten.quelle -notmatch '([0-9a-f]{40})') { throw "Revision in der Quelle nicht erkannt: $($Daten.quelle)" }
$Revision = $Matches[1].Substring(0, 12)
if (-not $Ziel) { $Ziel = Join-Path (Get-Location) "epm-ocr-modelle-$Revision.tar" }

function Pruefen([string]$Pfad, $Eintrag) {
    if (-not (Test-Path $Pfad)) { return $false }
    if ($Eintrag.groesse -and (Get-Item $Pfad).Length -ne [int64]$Eintrag.groesse) { return $false }
    if ($Eintrag.sha256) {
        return (Get-FileHash $Pfad -Algorithm SHA256).Hash.ToLower() -eq $Eintrag.sha256
    }
    # Sprachmodell fuer Diktate: SHA-1 der Datei, wie von whisper.cpp veroeffentlicht
    if ($Eintrag.sha1) {
        return (Get-FileHash $Pfad -Algorithm SHA1).Hash.ToLower() -eq $Eintrag.sha1
    }
    # kleine Textdateien: Git-Kennung = SHA-1 ueber "blob <Laenge>\0" + Inhalt
    $Bytes = [IO.File]::ReadAllBytes($Pfad)
    $Kopf = [Text.Encoding]::ASCII.GetBytes("blob $($Bytes.Length)`0")
    $Sha1 = [Security.Cryptography.SHA1]::Create()
    $Hash = -join ($Sha1.ComputeHash([byte[]]($Kopf + $Bytes)) | ForEach-Object { $_.ToString("x2") })
    return $Hash -eq $Eintrag.git_sha1
}

$Tmp = Join-Path ([IO.Path]::GetTempPath()) ("epm-ocr-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path (Join-Path $Tmp "dateien") | Out-Null
try {
    Write-Host "==> Modelle laden und pruefen (Quelle: $($Daten.quelle))"
    foreach ($Eintrag in $Daten.dateien) {
        $Pfad = Join-Path (Join-Path $Tmp "dateien") ($Eintrag.pfad -replace '/', '\')
        New-Item -ItemType Directory -Force -Path (Split-Path $Pfad) | Out-Null
        $Ok = $false
        foreach ($Versuch in 1..3) {
            try {
                $Url = if ($Eintrag.url) { $Eintrag.url } else { $Daten.quelle + $Eintrag.pfad }
                Invoke-WebRequest -Uri $Url -OutFile $Pfad -UseBasicParsing `
                    -UserAgent "EPM-Bau" -TimeoutSec 300
            } catch {
                Write-Host "Versuch ${Versuch}: $($Eintrag.pfad): $($_.Exception.Message)"
                Start-Sleep -Seconds (3 * $Versuch)
                continue
            }
            if (Pruefen $Pfad $Eintrag) { $Ok = $true; break }
            Write-Host "Pruefsumme falsch: $($Eintrag.pfad)"
            Remove-Item $Pfad -ErrorAction SilentlyContinue
        }
        if (-not $Ok -and $Eintrag.optional) {
            Write-Host "HINWEIS: $($Eintrag.pfad) fehlt (optional) - Diktate werden dann nicht abgeschrieben."
            continue
        }
        if (-not $Ok) { throw "Nicht geladen: $($Eintrag.pfad) - Zugang zu huggingface.co pruefen (Proxy?)." }
        Write-Host ("geladen    {0} ({1:N1} MB)" -f $Eintrag.pfad, ((Get-Item $Pfad).Length / 1MB))
    }
    [IO.File]::WriteAllText((Join-Path $Tmp "dateien\LIZENZ.txt"), $Daten.lizenz + "`n")
    Copy-Item $Liste (Join-Path $Tmp "modelle.json")
    # tar.exe gehoert seit Windows 10 (1803) zum System
    & tar.exe -C $Tmp -cf $Ziel modelle.json dateien
    if ($LASTEXITCODE -ne 0) { throw "tar fehlgeschlagen" }
    Write-Host ""
    Write-Host ("Fertig: {0} ({1:N0} MB)" -f $Ziel, ((Get-Item $Ziel).Length / 1MB))
    Write-Host "Weiter:  scp `"$Ziel`" epmadmin@TEST-VM:~/"
    Write-Host "         auf der Test-VM: sudo epm-ocr-modelle einspielen ~/$(Split-Path $Ziel -Leaf) ; sudo epm-update"
} finally {
    Remove-Item -Recurse -Force $Tmp -ErrorAction SilentlyContinue
}
