@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Doppio clic: avvia l'intero stack HyperSpace su Windows.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-tutto.ps1" %*
