#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/mesh_monitor.py
# Modulo promosso in produzione da HyperSpace R&D Sovereign Lab
# Prototipo sorgente: proto_biomimetic_nature_mesh_1793645722.py
# Data promozione: 2026-11-02T18:55:42.011728+00:00
# Autore: auto_promoter

class MeshMonitor:
    def __init__(self):
        self.flows = []  # list of (success, latency)
    def record(self, success, latency):
        self.flows.append((success, latency))
    def entropy(self):
        if not self.flows:
            return 0.0
        from math import log2
        counts = {}
        for s, l in self.flows:
            key = s  # group by success only
            counts[key] = counts.get(key, 0) + 1
        total = len(self.flows)
        ent = 0.0
        for c in counts.values():
            p = c / total
            if p > 0:
                ent -= p * log2(p)
        return ent
    def flow_effectiveness(self):
        if not self.flows:
            return 0.0
        successes = sum(1 for s,_ in self.flows if s)
        return successes / len(self.flows)


import unittest

class TestMeshMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = MeshMonitor()

    def test_empty_entropy(self):
        self.assertEqual(self.monitor.entropy(), 0.0)

    def test_single_flow_entropy(self):
        self.monitor.record(True, 10)
        self.assertAlmostEqual(self.monitor.entropy(), 0.0, places=5)

    def test_multiple_flows_entropy(self):
        self.monitor.record(True, 10)
        self.monitor.record(True, 20)
        self.monitor.record(False, 30)
        ent = self.monitor.entropy()
        self.assertGreater(ent, 0.0)
        self.assertLess(ent, 1.0)

    def test_empty_effectiveness(self):
        self.assertEqual(self.monitor.flow_effectiveness(), 0.0)

    def test_single_flow_effectiveness(self):
        self.monitor.record(True, 10)
        self.assertAlmostEqual(self.monitor.flow_effectiveness(), 1.0, places=5)

    def test_multiple_flows_effectiveness(self):
        self.monitor.record(True, 10)
        self.monitor.record(True, 20)
        self.monitor.record(False, 30)
        eff = self.monitor.flow_effectiveness()
        self.assertEqual(eff, 2/3)

if __name__ == '__main__':
    unittest.main()
