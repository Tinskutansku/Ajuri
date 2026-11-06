# AJURI - sammutus: backend, frontti ja tietokantakontti.
# Tietokannan data säilyy (docker compose stop, ei down -v).

$Juuri = Split-Path -Parent $PSScriptRoot
Set-Location $Juuri

function Sammuta($portti, $nimi) {
    # netstat -ano toimii ilman WMI:tä (Get-NetTCPConnection voi olla rikki).
    $pidit = netstat -ano -p TCP | Select-String -Pattern "LISTENING" |
        ForEach-Object { $osat = ($_.Line.Trim() -split "\s+"); if ($osat[1] -match ":$portti$") { $osat[-1] } } |
        Select-Object -Unique
    if (-not $pidit) {
        $pidit = netstat -ano -p TCPv6 | Select-String -Pattern "LISTENING" |
            ForEach-Object { $osat = ($_.Line.Trim() -split "\s+"); if ($osat[1] -match ":$portti$") { $osat[-1] } } |
            Select-Object -Unique
    }
    if (-not $pidit) {
        Write-Host "    $nimi ei ollut käynnissä"
        return
    }
    foreach ($pid_ in $pidit) {
        # uvicorn --reload ja npm käynnistävät lapsiprosesseja; /T sulkee
        # koko puun, jotta portti vapautuu varmasti.
        taskkill /PID $pid_ /T /F *> $null
    }
    Write-Host "    $nimi sammutettu" -ForegroundColor Green
}

Write-Host "==> Sammutetaan AJURI" -ForegroundColor Cyan
Sammuta 5173 "Frontti"
Sammuta 8000 "Backend"

# uvicornin reload-valvoja voi jäädä henkiin vaikka portti vapautui
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*uvicorn app.main:app*" } |
    ForEach-Object { taskkill /PID $_.ProcessId /T /F *> $null }

docker compose stop *> $null
Write-Host "    Tietokanta pysäytetty (data säilyy)" -ForegroundColor Green

# Suljetaan myös avoimiksi jääneet AJURI-ikkunat
Get-Process powershell -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like "AJURI *" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Valmis." -ForegroundColor Green
Start-Sleep -Seconds 3
