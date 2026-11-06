# AJURI - ajaa yhden palvelimen (backend tai frontti) omassa ikkunassaan.
# Käynnistetään scripts/kaynnista.ps1:stä, ei yleensä käsin.
#
# Miksi oma skripti: Windowsin konsolin "QuickEdit"-valintatila pysäyttää
# ohjelman heti kun ikkunaa klikataan (tekstin valinta alkaa), koska
# lokirivin kirjoitus konsoliin jää odottamaan valinnan päättymistä.
# Uvicorn kirjoittaa lokirivin jokaisesta pyynnöstä, joten yksi klikkaus
# jumitti koko backendin. Tämä skripti kytkee QuickEditin pois tästä
# ikkunasta ennen palvelimen käynnistystä.

param(
    [Parameter(Mandatory = $true)][string]$Otsikko,
    [Parameter(Mandatory = $true)][string]$Kansio,
    [Parameter(Mandatory = $true)][string]$Komento
)

$host.UI.RawUI.WindowTitle = $Otsikko

try {
    $maaritys = @"
[DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int nStdHandle);
[DllImport("kernel32.dll")] public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll")] public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
"@
    $k = Add-Type -MemberDefinition $maaritys -Name Konsoli -Namespace AjuriKonsoli -PassThru
    $syote = $k::GetStdHandle(-10)        # STD_INPUT_HANDLE
    $tila = [uint32]0
    if ($k::GetConsoleMode($syote, [ref]$tila)) {
        $QUICK_EDIT = [uint32]0x0040
        $EXTENDED_FLAGS = [uint32]0x0080   # pakollinen, jotta QuickEditin poisto pysyy
        $uusi = ($tila -band (-bnot $QUICK_EDIT)) -bor $EXTENDED_FLAGS
        [void]$k::SetConsoleMode($syote, $uusi)
    }
} catch {
    Write-Host "Huom: QuickEditin poisto ei onnistunut ($_). Älä klikkaa tätä ikkunaa palvelimen ollessa käynnissä." -ForegroundColor Yellow
}

Write-Host "$Otsikko - tämän ikkunan klikkaaminen ei pysäytä palvelinta. Sulje: Ctrl+C tai 'Sammuta AJURI.cmd'." -ForegroundColor DarkGray
Set-Location $Kansio
Invoke-Expression $Komento
