#Requires -Version 5.1
<#
.SYNOPSIS
    Generate a city JSON export and optionally open the isometric concept viewer.
.PARAMETER Seed
    Master seed for the city. Default: 1.
.PARAMETER Profile
    City profile: generic_dense, manhattan, barcelona_eixample, paris_haussmann, london_organic.
.PARAMETER Coast
    Coastline side: none, north, south, east, west, random.
.PARAMETER Width
    Map width in cells.
.PARAMETER Height
    Map height in cells.
.PARAMETER Out
    Output JSON file path. Defaults to city_seed_<N>.json in the project root.
.PARAMETER OpenViewer
    Open city_viewer.html with matching seed/profile/coast/size parameters.
.EXAMPLE
    .\generate_city.ps1 -Seed 42 -Profile manhattan -Coast west
.EXAMPLE
    .\generate_city.ps1 -Seed 7 -Profile paris_haussmann -Width 128 -Height 96 -OpenViewer
#>
param(
    [uint32]$Seed    = 1,
    [string]$Profile = 'generic_dense',
    [string]$Coast   = 'random',
    [int]   $Width   = 96,
    [int]   $Height  = 72,
    [string]$Out     = '',
    [switch]$OpenViewer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = $PSScriptRoot
$BuildDir = Join-Path $ProjectRoot 'build'
$ExporterCandidates = @(
    (Join-Path $BuildDir 'mapping_algorithm\cpp\Release\mapping_city_exporter.exe'),
    (Join-Path $BuildDir 'mapping_algorithm\cpp\Debug\mapping_city_exporter.exe'),
    (Join-Path $BuildDir 'mapping_algorithm\cpp\mapping_city_exporter.exe')
)

$Exporter = $ExporterCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Exporter) {
    Write-Host ''
    Write-Host '  ERROR: mapping_city_exporter.exe not found.' -ForegroundColor Red
    Write-Host '  Checked:' -ForegroundColor DarkGray
    foreach ($Candidate in $ExporterCandidates) {
        Write-Host "    $Candidate" -ForegroundColor DarkGray
    }
    Write-Host ''
    Write-Host '  Build the project first:' -ForegroundColor Yellow
    Write-Host '    cmake -S . -B build -G "Visual Studio 17 2022" -A x64' -ForegroundColor Cyan
    Write-Host '    cmake --build build --config Release' -ForegroundColor Cyan
    Write-Host ''
    exit 1
}

if ($Out -eq '') {
    $Out = Join-Path $ProjectRoot "city_seed_$Seed.json"
}

Write-Host ''
Write-Host '  CITY GENERATOR' -ForegroundColor Cyan
Write-Host "  seed=$Seed  profile=$Profile  coast=$Coast  ${Width}x${Height}" -ForegroundColor DarkGray
Write-Host ''

$Args = @(
    '--seed',    $Seed
    '--profile', $Profile
    '--coast',   $Coast
    '--width',   $Width
    '--height',  $Height
    '--out',     $Out
)

& $Exporter @Args
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '  Exporter failed - check parameters above.' -ForegroundColor Red
    exit $LASTEXITCODE
}

$Size = (Get-Item -LiteralPath $Out).Length
$Viewer = Join-Path $ProjectRoot 'city_viewer.html'
Write-Host "  Output : $Out  ($([math]::Round($Size / 1KB, 1)) KB)" -ForegroundColor Green
Write-Host ''
Write-Host '  -----------------------------------------' -ForegroundColor DarkGray
Write-Host '  Output JSON:' -ForegroundColor Yellow
Write-Host "    $Out" -ForegroundColor White
Write-Host '  Viewer:' -ForegroundColor Yellow
Write-Host "    $Viewer" -ForegroundColor White
Write-Host '  Note: the HTML viewer can load this JSON by drag/drop and also has' -ForegroundColor DarkGray
Write-Host '        a mirrored JS generator for quick visual exploration.' -ForegroundColor DarkGray
Write-Host '  -----------------------------------------' -ForegroundColor DarkGray
Write-Host ''

if ($OpenViewer) {
    $ViewerUri = [System.Uri]::new((Resolve-Path -LiteralPath $Viewer).Path).AbsoluteUri
    $Query = '?seed={0}&profile={1}&coast={2}&size={3}x{4}' -f
        [System.Uri]::EscapeDataString([string]$Seed),
        [System.Uri]::EscapeDataString($Profile),
        [System.Uri]::EscapeDataString($Coast),
        [System.Uri]::EscapeDataString([string]$Width),
        [System.Uri]::EscapeDataString([string]$Height)
    Start-Process ($ViewerUri + $Query)
}
