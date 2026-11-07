#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Aggiunge una riga con l'ora al registro di lavoro: scripts/syndwars_log.sh "testo"
echo "$(date +%H:%M:%S) $*" >> "$(dirname "$0")/../data/nightly/syndwars_lavoro.log"
