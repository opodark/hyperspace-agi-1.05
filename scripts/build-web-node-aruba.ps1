# SPDX-License-Identifier: Apache-2.0
param(
    [string]$GatewayUrl = "https://mesh.zerozerocomputer.it",
    [string]$OutputDir = "dist/web-node-aruba"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$target = [IO.Path]::GetFullPath((Join-Path $repo $OutputDir))
$distRoot = [IO.Path]::GetFullPath((Join-Path $repo "dist"))
if (-not $target.StartsWith($distRoot + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputDir deve restare dentro $distRoot"
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $target "src") | Out-Null
Copy-Item -LiteralPath (Join-Path $repo "web-node/join.html") `
    -Destination (Join-Path $target "index.html") -Force
Get-ChildItem -Path (Join-Path $repo "web-node") -Filter "*.html" | ForEach-Object {
    if ($_.Name -ne "join.html" -and $_.Name -ne "index.html") {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $target $_.Name) -Force
    }
}
$htaccess = Join-Path $repo "web-node/.htaccess"
if (Test-Path -LiteralPath $htaccess) {
    Copy-Item -LiteralPath $htaccess -Destination (Join-Path $target ".htaccess") -Force
}
Get-ChildItem -Path (Join-Path $repo "web-node/src") -Filter "*.js" | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $target "src/$($_.Name)") -Force
}



$escapedUrl = $GatewayUrl.TrimEnd("/").Replace("\", "\\").Replace('"', '\"')
$config = @"
// SPDX-License-Identifier: Apache-2.0
window.HYPERSPACE_JOIN = Object.freeze({
  gatewayUrl: "$escapedUrl",
  siteName: "ZeroZeroComputer",
  meshName: "HyperSpace",
});
"@
[IO.File]::WriteAllText((Join-Path $target "join-config.js"), $config,
    [Text.UTF8Encoding]::new($false))

$zip = "$target.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $target "*") -DestinationPath $zip
Write-Host "Pacchetto Aruba: $zip"
