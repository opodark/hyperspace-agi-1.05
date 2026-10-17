# SPDX-License-Identifier: Apache-2.0
$wshell = New-Object -ComObject WScript.Shell
$startupDir = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupDir "HyperSpace Bonsai 2.lnk"
$s = $wshell.CreateShortcut($shortcutPath)
$s.TargetPath = "powershell.exe"
$s.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\start_bonsai_daemon.ps1`""
$s.WorkingDirectory = Split-Path -Parent $PSScriptRoot
$s.Description = "HyperSpace Bonsai 2 (27B Abliterated) LLM Server"
$s.Save()
Write-Host "Created shortcut: $shortcutPath"
