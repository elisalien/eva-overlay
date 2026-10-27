<#
.SYNOPSIS
  Installs the EVA-Responsive Wire source for Resolume Arena / Wire (Windows).

.DESCRIPTION
  1. Installs the two bundled fonts for the current user (no admin rights needed).
  2. Copies the patch to <Documents>\Resolume Wire\Patches\EVA-Responsive and points the
     .wire file at the shader and the atlas in that folder.
  Restart Wire and Arena afterwards: new fonts only show after a restart.

.PARAMETER PatchesDir
  Resolume Wire patches folder. Default: <Documents>\Resolume Wire\Patches.

.PARAMETER NoFonts
  Skip the font install (fonts already installed).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1
#>
param(
    [string]$PatchesDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Resolume Wire\Patches'),
    [switch]$NoFonts
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$name = 'EVA-Responsive'

# Fonts, per user. A font already in the user font folder is left as it is.
if (-not $NoFonts) {
    $fontDir = Join-Path $env:LOCALAPPDATA 'Microsoft\Windows\Fonts'
    $fontReg = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Fonts'
    New-Item -ItemType Directory -Force $fontDir | Out-Null
    $fonts = @{
        'NotoSerifCJKjp-Black.otf'       = 'Noto Serif CJK JP Black (OpenType)'
        'ShipporiMinchoB1-ExtraBold.ttf' = 'Shippori Mincho B1 ExtraBold (TrueType)'
    }
    foreach ($file in $fonts.Keys) {
        $dst = Join-Path $fontDir $file
        if (Test-Path $dst) { Write-Host "font already installed: $file"; continue }
        Copy-Item (Join-Path $here "fonts\$file") $dst
        New-ItemProperty -Path $fontReg -Name $fonts[$file] -Value $dst -PropertyType String -Force | Out-Null
        Write-Host "font: $file"
    }
}

# Patch.
$target = Join-Path $PatchesDir $name
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item (Join-Path $here "$name\EVA_Responsive.isf"), (Join-Path $here "$name\eva_atlas.png") $target -Force
$wire = [IO.File]::ReadAllText((Join-Path $here "$name\$name.wire"), [Text.Encoding]::UTF8)
$posix = $target -replace '\\', '/'
$wire = [regex]::Replace($wire, '"main": "[^"]*/(EVA_Responsive\.isf|eva_atlas\.png)"',
    { param($m) '"main": "' + $posix + '/' + $m.Groups[1].Value + '"' })
[IO.File]::WriteAllText((Join-Path $target "$name.wire"), $wire, (New-Object Text.UTF8Encoding($false)))
Write-Host "patch: $target"
Write-Host 'Done. Restart Resolume Wire and Arena, then add EVA-Responsive from the Wire sources.'
