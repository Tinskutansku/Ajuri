# AJURI - käynnistys yhdellä komennolla (Windows PowerShell 5.1+).
# Käynnistetään yleensä tuplaklikkaamalla juuren "Käynnistä AJURI.cmd".
#
#   -Seed   aja demodatan seed (idempotentti, ei luo tuplia)
#
# Skripti on turvallinen ajaa uudelleen: jos backend tai frontti on jo
# käynnissä, niitä ei käynnistetä toista kertaa.

param([switch]$Seed)

$ErrorActionPreference = "Stop"
$Juuri = Split-Path -Parent $PSScriptRoot
Set-Location $Juuri

# Loki jokaisesta ajosta: kaynnistys.log projektin juuressa (gitignoressa).
try { Start-Transcript -Path (Join-Path $Juuri "kaynnistys.log") -Force | Out-Null } catch {}

# Odottamaton virhe ei saa sulkea ikkunaa hiljaa.
trap {
    Write-Host ""
    Write-Host "ODOTTAMATON VIRHE: $_" -ForegroundColor Red
    Write-Host "Rivi: $($_.InvocationInfo.ScriptLineNumber)  Loki: kaynnistys.log"
    try { Stop-Transcript | Out-Null } catch {}
    Read-Host "Paina Enter sulkeaksesi"
    exit 1
}

function Vaihe($teksti) { Write-Host ""; Write-Host "==> $teksti" -ForegroundColor Cyan }
function Ok($teksti) { Write-Host "    $teksti" -ForegroundColor Green }
function Virhe($teksti) {
    Write-Host ""
    Write-Host "VIRHE: $teksti" -ForegroundColor Red
    Write-Host ""
    try { Stop-Transcript | Out-Null } catch {}
    Read-Host "Paina Enter sulkeaksesi"
    exit 1
}

function PorttiKaytossa($portti) {
    $yhteys = Get-NetTCPConnection -LocalPort $portti -State Listen -ErrorAction SilentlyContinue
    return [bool]$yhteys
}

function OdotaPortti($portti, $sekunnit) {
    # Ei HTTP-kyselyä: Windows PowerShell 5.1:n Invoke-WebRequest voi
    # kulkea järjestelmän välityspalvelimen kautta tai jumittua localhostin
    # IPv6/IPv4-valintaan. Kuunteleva portti riittää merkiksi siitä, että
    # palvelin on ylhäällä (Vite kuuntelee ::1:ssä, uvicorn 127.0.0.1:ssä).
    $loppu = (Get-Date).AddSeconds($sekunnit)
    while ((Get-Date) -lt $loppu) {
        if (PorttiKaytossa $portti) { return $true }
        Start-Sleep -Seconds 1
        Write-Host "." -NoNewline
    }
    return $false
}

function DockerValmis {
    # Docker kirjoittaa stderriin kun moottori ei ole käynnissä; ei haluta
    # että $ErrorActionPreference = Stop kaataa skriptin siihen.
    $vanha = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    docker info *> $null
    $tulos = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $vanha
    return $tulos
}

$Python = Join-Path $Juuri "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Virhe "venv puuttuu. Aja kerran: python -m venv venv ; venv\Scripts\pip install -r requirements.txt"
}

# --- 1. Docker Desktop ---
Vaihe "Docker Desktop"
if (-not (DockerValmis)) {
    $dockerExe = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerExe)) { Virhe "Docker Desktopia ei löytynyt: $dockerExe" }
    Write-Host "    Käynnistetään Docker Desktop, odotetaan moottoria (max 3 min)..."
    Start-Process $dockerExe
    $loppu = (Get-Date).AddMinutes(3)
    while (-not (DockerValmis)) {
        if ((Get-Date) -gt $loppu) { Virhe "Docker ei käynnistynyt 3 minuutissa. Avaa Docker Desktop käsin ja aja uudelleen." }
        Start-Sleep -Seconds 3
        Write-Host "." -NoNewline
    }
    Write-Host ""
}
Ok "Docker on käynnissä"

# --- 2. Tietokanta ---
Vaihe "Tietokanta (PostgreSQL)"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Ok ".env luotu .env.examplesta"
}
docker compose up -d --wait db
if ($LASTEXITCODE -ne 0) { Virhe "Tietokanta ei käynnistynyt (docker compose up -d db)." }
Ok "Tietokanta on käynnissä portissa 5433"

# --- 3. Migraatiot ---
Vaihe "Migraatiot"
& $Python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Virhe "alembic upgrade head epäonnistui." }
Ok "Kanta on ajan tasalla"

if ($Seed) {
    Vaihe "Demodata"
    & $Python -m app.seed
    if ($LASTEXITCODE -ne 0) { Virhe "Seed epäonnistui." }
}

# --- 4. Backend omaan ikkunaan ---
Vaihe "Backend (http://localhost:8000)"
if (PorttiKaytossa 8000) {
    Ok "Portti 8000 on jo käytössä - backend on ilmeisesti jo päällä, ei käynnistetä uudelleen"
} else {
    $komento = "`$host.UI.RawUI.WindowTitle = 'AJURI backend'; Set-Location '$Juuri'; & '$Python' -m uvicorn app.main:app --reload"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $komento
    if (-not (OdotaPortti 8000 180)) {
        Write-Host ""
        Virhe "Backend ei käynnistynyt 3 minuutissa. Katso virhe 'AJURI backend' -ikkunasta."
    }
    Write-Host ""
    Ok "Backend vastaa"
}

# --- 5. Frontti omaan ikkunaan ---
Vaihe "Frontti (http://localhost:5173)"
$Frontend = Join-Path $Juuri "frontend"
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "    node_modules puuttuu, ajetaan npm install..."
    Push-Location $Frontend
    npm install
    $npmOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if (-not $npmOk) { Virhe "npm install epäonnistui." }
}
if (PorttiKaytossa 5173) {
    Ok "Portti 5173 on jo käytössä - frontti on ilmeisesti jo päällä, ei käynnistetä uudelleen"
} else {
    # --strictPort: jos 5173 olisi varattu, Vite ei hyppää toiseen porttiin
    # (CORS sallii vain 5173, muuten tulisi "Failed to fetch").
    $komento = "`$host.UI.RawUI.WindowTitle = 'AJURI frontti'; Set-Location '$Frontend'; npm run dev -- --strictPort"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $komento
    if (-not (OdotaPortti 5173 180)) {
        Write-Host ""
        Virhe "Frontti ei käynnistynyt 3 minuutissa. Katso virhe 'AJURI frontti' -ikkunasta."
    }
    Write-Host ""
    Ok "Frontti vastaa"
}

# --- 6. Selain ---
Start-Process "http://localhost:5173"

Write-Host ""
Write-Host "AJURI on käynnissä." -ForegroundColor Green
Write-Host "  Sovellus: http://localhost:5173"
Write-Host "  API:      http://localhost:8000/docs"
Write-Host "  Sammutus: tuplaklikkaa 'Sammuta AJURI.cmd'"
Write-Host ""
try { Stop-Transcript | Out-Null } catch {}
Start-Sleep -Seconds 5
