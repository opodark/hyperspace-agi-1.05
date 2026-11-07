#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Segue dal Mac l'avanzamento di una prova di par_check.sh sull'OMEN: segui.sh <tag>
exec ssh -o BatchMode=yes opoda@100.104.238.125 "wsl -d swbuild -u root -- tail -n 50 -f /tmp/par_${1:?tag}/avanzamento.log"
