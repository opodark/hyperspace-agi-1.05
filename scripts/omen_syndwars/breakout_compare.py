#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Confronta due prove di breakout_check.sh (tag A e B) ai turni salvati. Uso: breakout_compare.py <tagA> <tagB>
I puntatori delle liste (ListNext, ListPvNxPtr) sono indirizzi: si azzerano, perche' i dati si spostano fra binari."""
import sys

TURNI = (410, 430, 450, 480, 520, 600, 700, 900)
LAYOUT = {"balls": (40, ((32, 8),)), "bonus": (24, ((16, 8),)), "screen": (0, ()), "bricks": (0, ())}


def load(tag, turn, name):
    data = bytearray(open(f"/tmp/bo_{tag}_{turn}_{name}.bin", "rb").read())
    size, masks = LAYOUT[name]
    if size:
        for base in range(0, len(data) - len(data) % size, size):
            for offset, length in masks:
                data[base + offset:base + offset + length] = bytes(length)
    return bytes(data)


a, b = sys.argv[1], sys.argv[2]
bad = 0
for turn in TURNI:
    row = []
    for name in LAYOUT:
        same = load(a, turn, name) == load(b, turn, name)
        row.append(f"{name}={'uguale' if same else 'DIVERSO'}")
        bad += not same
    print(turn, " ".join(row))
print("differenze:", bad)
