# SPDX-License-Identifier: Apache-2.0
"""Test suite per la generazione preventivi e fatture PMI (shared/business_docs.py)."""
import os
import tempfile
import unittest
from pathlib import Path

from shared.business_docs import BusinessDocument, DocumentItem, DocumentParty


class BusinessDocsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.issuer = DocumentParty(
            name="Idraulica & Servizi Rossi S.r.l.",
            address="Via Roma 10, 24121 Bergamo (BG)",
            vat_number="IT01234567890",
            email="amministrazione@rossi-impianti.it",
            phone="+39 035 123456",
        )
        self.client = DocumentParty(
            name="Studio Commerciale Bianchi",
            address="Piazza Dante 4, 20121 Milano (MI)",
            vat_number="IT09876543211",
            email="contabilita@studiobianchi.it",
        )

    def test_calcolo_totali_semplice(self):
        doc = BusinessDocument(
            doc_type="PREVENTIVO",
            number="PREV-2026-001",
            date="31/10/2026",
            issuer=self.issuer,
            client=self.client,
            items=[
                DocumentItem("Manutenzione ordinaria impianto termico", quantity=1.0, unit_price=150.0, vat_rate=22.0),
                DocumentItem("Sostituzione valvola termostatica", quantity=2.0, unit_price=45.0, vat_rate=22.0),
            ],
        )
        totals = doc.calculate_totals()
        self.assertEqual(totals["subtotal_net"], 240.0)
        self.assertEqual(totals["total_vat"], 52.8)
        self.assertEqual(totals["total_gross"], 292.8)
        self.assertEqual(totals["net_payable"], 292.8)

    def test_calcolo_con_ritenuta_dacconto(self):
        doc = BusinessDocument(
            doc_type="FATTURA",
            number="FATT-2026-042",
            date="31/10/2026",
            issuer=self.issuer,
            client=self.client,
            items=[
                DocumentItem("Consulenza tecnica di adeguamento", quantity=10.0, unit_price=80.0, vat_rate=22.0),
            ],
            withholding_tax_rate=20.0,  # 20% su imponibile
        )
        totals = doc.calculate_totals()
        self.assertEqual(totals["subtotal_net"], 800.0)
        self.assertEqual(totals["total_vat"], 176.0)
        self.assertEqual(totals["withholding"], 160.0)
        self.assertEqual(totals["total_gross"], 976.0)
        self.assertEqual(totals["net_payable"], 816.0)

    def test_generazione_pdf_reale(self):
        doc = BusinessDocument(
            doc_type="PREVENTIVO",
            number="PREV-2026-088",
            date="31/10/2026",
            issuer=self.issuer,
            client=self.client,
            items=[
                DocumentItem("Rifacimento tubazioni bagno principale", quantity=1.0, unit_price=850.0, vat_rate=10.0),
                DocumentItem("Raccordi e materiale di consumo", quantity=1.0, unit_price=120.0, vat_rate=22.0),
            ],
            notes="Preventivo valido 30 giorni. Consegna prevista entro 5 giorni lavorativi dall'accettazione.",
        )
        output_pdf = Path(self.temp_dir.name) / "preventivo_test.pdf"
        rendered = doc.render_pdf(output_pdf)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 1000)
        # Magic bytes di un file PDF valido
        with open(output_pdf, "rb") as f:
            header = f.read(5)
            self.assertEqual(header, b"%PDF-")


if __name__ == "__main__":
    unittest.main()
