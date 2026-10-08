# SPDX-License-Identifier: Apache-2.0
import ast
import hashlib
import json
import re
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
import os

from flask import Blueprint, Flask, jsonify, request
from shared.forge_skills import (ANYDOC_BUNDLE_DIR, ECC_BUNDLE_DIR,
                                 FIRECRAWL_SKILLS_BUNDLE_DIR, AGENCY_AGENTS_BUNDLE_DIR,
                                 load_agency_agents_bundle, attach_skills,
                                 load_anydoc_bundle, load_ecc_bundle,
                                 load_firecrawl_skills_bundle, source_hash)


def _symlink_creation_available() -> bool:
    """Windows richiede privilegi (o Developer Mode) per creare un symlink.

    Senza, il caso 'symlink' del test non e' verificabile: meglio saltarlo
    dichiarandolo che fingere che sia passato.
    """
    with tempfile.TemporaryDirectory() as tmp:
        try:
            (Path(tmp) / "link").symlink_to(Path(tmp) / "target")
        except (OSError, NotImplementedError):
            return False
    return True


SYMLINKS_AVAILABLE = _symlink_creation_available()


class BundleTests(unittest.TestCase):
    def test_pinned_bundle_has_license_and_two_verified_sources(self):
        items = load_ecc_bundle(ECC_BUNDLE_DIR)
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertEqual(source_hash(item["source"]), item["provenance"]["sha256"])
            self.assertIn("Permission is hereby granted", item["provenance"]["license_text"])

    def test_tampering_symlinks_and_unexpected_files_rejected(self):
        for change in ("tamper", "symlink", "manifest"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "ecc"
                shutil.copytree(ECC_BUNDLE_DIR, root)
                target = root / "skills/security-review/SKILL.md"
                if change == "tamper":
                    target.write_text("changed")
                elif change == "symlink":
                    if not SYMLINKS_AVAILABLE:
                        self.skipTest("questo filesystem/utente non puo' creare symlink")
                    target.unlink()
                    target.symlink_to(ECC_BUNDLE_DIR / "skills/security-review/SKILL.md")
                else:
                    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
                    manifest["files"]["../../outside"] = "0" * 64
                    (root / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    load_ecc_bundle(root)


class AgencyAgentsBundleTests(unittest.TestCase):
    def test_three_short_adaptations_have_verified_upstream_and_fit_context(self):
        items = load_agency_agents_bundle(AGENCY_AGENTS_BUNDLE_DIR)
        self.assertEqual(len(items), 3)
        for item in items:
            self.assertNotIn('status', item)
            self.assertEqual(item['permissions'], [])
            self.assertEqual(source_hash(item['source']), item['provenance']['sha256'])
            self.assertLess(len(item['source'].encode()), 4000)
        for name in ('multi-agent-architect', 'code-reviewer', 'technical-writer'):
            self.assertTrue(any(item['id'].startswith(f'agency-{name}-') for item in items))

    def test_tampered_adaptation_or_upstream_is_rejected(self):
        for target in ('skills/code-reviewer/SKILL.md', 'upstream/engineering-code-reviewer.md'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / 'agency-agents'
                shutil.copytree(AGENCY_AGENTS_BUNDLE_DIR, root)
                (root / target).write_text('tampered', encoding='utf-8')
                with self.assertRaises(ValueError):
                    load_agency_agents_bundle(root)


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.item = {"type": "skill", "status": "approved", "version": 1,
                     "source": "# Example\nInspect the result.",
                     "approved_source_sha256": source_hash("# Example\nInspect the result.")}

    def test_opt_in_only_and_extension_not_forwarded(self):
        data = {"messages": [{"role": "user", "content": "Hello"}]}
        self.assertEqual(attach_skills(data, lambda _: self.fail("unexpected load")), data)
        selected = dict(data, hyperspace_skills=["example"])
        result = attach_skills(selected, lambda _: self.item)
        self.assertNotIn("hyperspace_skills", result)
        self.assertIn(self.item["source"], result["messages"][0]["content"])
        self.assertEqual(result["messages"][-1], data["messages"][0])
        self.assertEqual(len(data["messages"]), 1)

    def test_draft_disabled_modified_and_oversized_skills_rejected(self):
        for field, value in (("status", "draft"), ("status", "disabled"),
                             ("type", "tool"), ("source", "tampered"),
                             ("approved_source_sha256", None)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                attach_skills({"hyperspace_skills": ["example"]},
                              lambda _: dict(self.item, **{field: value}))
        big = "x" * 24000
        with self.assertRaises(ValueError):
            attach_skills({"hyperspace_skills": ["example"]}, lambda _: dict(
                self.item, source=big, approved_source_sha256=source_hash(big)))

    def test_invalid_selection_and_path_traversal(self):
        for ids in (None, "example", ["../secret"], ["a", "a"], ["a", "b", "c"], [3]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                attach_skills({"hyperspace_skills": ids}, lambda _: self.fail("invalid ID read"))

    def test_both_ecc_skills_fit_context_budget(self):
        items = load_ecc_bundle(ECC_BUNDLE_DIR)
        by_id = {item["id"]: dict(item, status="approved", version=1,
                                  approved_source_sha256=source_hash(item["source"])) for item in items}
        result = attach_skills({"hyperspace_skills": list(by_id), "messages": [
            {"role": "system", "content": "System"}, {"role": "user", "content": "Task"}]}, by_id.__getitem__)
        self.assertEqual(result["messages"][0]["content"], "System")
        self.assertEqual(result["messages"][1]["role"], "user")


class ForgeRoutesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = Flask(__name__)
        app.testing = True
        self.ns = dict(globals(), app=app, FORGE_DIR=self.tmp.name, FORGE_ADMIN_TOKEN="test-token",
                       _forge_lock=threading.Lock(), _FORGE_TYPES={"tool", "skill"},
                       _FORGE_STATES={"draft", "review", "approved", "disabled"},
                       push_log=lambda *args, **kwargs: None,
                       # la rotta di chat registra le sue rotte su un blueprint: nello
                       # scope isolato un blueprint finto basta, il test esercita
                       # l'accostamento fra forge e skill, non il montaggio
                       _bp=Blueprint("chat-test", __name__))
        # Il forge sta in main.py, la rotta che legge gli skill sta in cp/chat.py:
        # il test le prende entrambe, perche' e' il loro accostamento che prova.
        # encoding esplicito: i file hanno caratteri non-ASCII (i banner di sezione)
        # e su Windows la codifica di default del sistema non e' UTF-8.
        radice = Path(__file__).parents[1]
        nomi_per_file = {
            radice / "control-plane/cp/forge.py": {
                "_forge_path", "_forge_write", "_forge_authorized", "_forge_validate",
                "_forge_read_skill", "forge_import_ecc", "forge_update", "forge_status"},
            radice / "control-plane/cp/chat.py": {"v1_chat_completions"},
        }
        nodes = []
        for percorso, nomi in nomi_per_file.items():
            nodes += [node for node in ast.parse(percorso.read_text(encoding="utf-8")).body
                      if isinstance(node, ast.FunctionDef) and node.name in nomi]
        # La rotta riceve i suoi oggetti per contesto: lo scope isolato ne ha
        # bisogno con la stessa forma, o il test eserciterebbe un percorso che in
        # produzione non esiste.
        self.ns["_contesto"] = SimpleNamespace(
            advanced_config={"ollama": {"url": "http://ollama", "defaultModel": "modello"}},
            tasks={}, cp_identity={},
            forge_read_skill=self.ns.get("_forge_read_skill"))
        source = radice / "control-plane/main.py"
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), self.ns)
        # il blueprint raccoglie le rotte ma non le registra finche' qualcuno non
        # lo monta: senza questo il client non trova /v1/chat/completions e
        # risponde 404 su tutto
        app.register_blueprint(self.ns["_bp"])
        self.client = app.test_client()
        self.headers = {"X-Hyperspace-Forge-Token": "test-token"}

    def test_import_auth_idempotence_and_reapproval_after_edit(self):
        self.assertEqual(self.client.post("/forge/import/ecc").status_code, 403)
        response = self.client.post("/forge/import/ecc", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        artifact_id = response.json["artifacts"][0]["id"]
        item = self.ns["_forge_read_skill"](artifact_id)
        self.assertEqual(item["status"], "draft")
        approved = self.client.post(f"/forge/artifacts/{artifact_id}/status", headers=self.headers,
                                    json={"status": "approved"})
        self.assertEqual(approved.json["approved_source_sha256"], source_hash(item["source"]))
        self.client.put(f"/forge/artifacts/{artifact_id}", json={"source": "# Local revision\n"})
        again = self.client.post("/forge/import/ecc", headers=self.headers)
        self.assertFalse(any(item["created"] for item in again.json["artifacts"]))
        edited = self.ns["_forge_read_skill"](artifact_id)
        self.assertEqual(edited["source"], "# Local revision\n")
        self.assertEqual(edited["status"], "draft")
        self.assertNotIn("approved_source_sha256", edited)
        self.assertIn("provenance", edited)
        rejected = self.client.post("/v1/chat/completions", json={"hyperspace_skills": [artifact_id]})
        self.assertEqual(rejected.status_code, 400)


if __name__ == "__main__":
    unittest.main()


# Regressioni 1.05 conservate dopo lo split cp/.
class AnydocBundleTests(unittest.TestCase):

    def test_pinned_bundle_has_one_verified_office_skill(self):
        items = load_anydoc_bundle(ANYDOC_BUNDLE_DIR)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['type'], 'skill')
        self.assertEqual(item['generator'], 'anydoc-import')
        self.assertTrue(item['id'].startswith('anydoc-convert-documents-to-markdown-'))
        self.assertEqual(item['provenance']['repository'], 'https://github.com/firecrawl/anydoc')
        self.assertRegex(item['provenance']['commit'], '^[0-9a-f]{40}$')
        self.assertEqual(item['provenance']['license'], 'MIT')
        self.assertEqual(source_hash(item['source']), item['provenance']['sha256'])
        self.assertIn('Permission is hereby granted', item['provenance']['license_text'])

    def test_tampering_and_wrong_provenance_rejected(self):
        for change in ('tamper', 'repository'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / 'anydoc'
                shutil.copytree(ANYDOC_BUNDLE_DIR, root)
                if change == 'tamper':
                    (root / 'skills/convert-documents-to-markdown/SKILL.md').write_text('changed')
                else:
                    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
                    manifest['repository'] = 'https://example.com/other'
                    (root / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    load_anydoc_bundle(root)

class AnydocForgeRouteTests(unittest.TestCase):
    """`POST /forge/import/anydoc` eseguito davvero, non solo letto nel sorgente."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = Flask(__name__)
        app.testing = True
        self.ns = dict(globals(), app=app, FORGE_DIR=self.tmp.name, FORGE_ADMIN_TOKEN='test-token', _forge_lock=threading.Lock(), _FORGE_TYPES={'tool', 'skill', 'patch'}, _FORGE_STATES={'draft', 'review', 'approved', 'disabled'}, load_anydoc_bundle=load_anydoc_bundle, ANYDOC_BUNDLE_DIR=ANYDOC_BUNDLE_DIR, push_log=lambda *args, **kwargs: None)
        self.ns['_bp'] = Blueprint('forge-anydoc', __name__)
        source = Path(__file__).parents[1] / 'control-plane/cp/forge.py'
        names = {'_forge_path', '_forge_write', '_forge_authorized', '_forge_validate', '_forge_read_skill', 'forge_import_anydoc'}
        nodes = [node for node in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(node, ast.FunctionDef) and node.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), self.ns)
        app.register_blueprint(self.ns['_bp'])
        self.client = app.test_client()
        self.headers = {'X-Hyperspace-Forge-Token': 'test-token'}

    def test_import_requires_token_and_is_idempotent(self):
        self.assertEqual(self.client.post('/forge/import/anydoc', json={}).status_code, 403)
        response = self.client.post('/forge/import/anydoc', headers=self.headers, json={})
        self.assertEqual(response.status_code, 200)
        entry = response.json['artifacts'][0]
        self.assertTrue(entry['created'])
        item = self.ns['_forge_read_skill'](entry['id'])
        self.assertEqual(item['status'], 'draft')
        self.assertEqual(item['type'], 'skill')
        self.assertTrue(item['validation']['valid'])
        again = self.client.post('/forge/import/anydoc', headers=self.headers, json={})
        self.assertFalse(any((item['created'] for item in again.json['artifacts'])))


class AgencyAgentsForgeRouteTests(unittest.TestCase):
    def test_token_draft_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = Flask(__name__)
            app.testing = True
            scope = dict(globals(), FORGE_DIR=tmp, FORGE_ADMIN_TOKEN='test-token',
                         _forge_lock=threading.Lock(), _FORGE_TYPES={'tool', 'skill', 'patch'},
                         _FORGE_STATES={'draft', 'review', 'approved', 'disabled'},
                         _bp=Blueprint('forge-agency', __name__))
            source = Path(__file__).parents[1] / 'control-plane/cp/forge.py'
            names = {'_forge_path', '_forge_write', '_forge_authorized', '_forge_validate',
                     '_forge_read_skill', 'forge_import_agency_agents'}
            nodes = [node for node in ast.parse(source.read_text(encoding='utf-8')).body
                     if isinstance(node, ast.FunctionDef) and node.name in names]
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
            app.register_blueprint(scope['_bp'])
            client = app.test_client()
            self.assertEqual(client.post('/forge/import/agency-agents').status_code, 403)
            headers = {'X-Hyperspace-Forge-Token': 'test-token'}
            response = client.post('/forge/import/agency-agents', headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json['artifacts']), 3)
            self.assertTrue(all(entry['created'] for entry in response.json['artifacts']))
            for entry in response.json['artifacts']:
                self.assertEqual(scope['_forge_read_skill'](entry['id'])['status'], 'draft')
            again = client.post('/forge/import/agency-agents', headers=headers)
            self.assertTrue(all(not entry['created'] for entry in again.json['artifacts']))

class FirecrawlSkillsBundleTests(unittest.TestCase):
    """Il catalogo testuale Firecrawl: quattro voci, verificate e inerti."""

    def test_catalogue_bundle_has_four_verified_reference_skills(self):
        items = load_firecrawl_skills_bundle(FIRECRAWL_SKILLS_BUNDLE_DIR)
        self.assertEqual(len(items), 4)
        self.assertEqual({item['id'].rsplit('-', 1)[0] for item in items}, {f'firecrawl-skills-{name}' for name in ('firecrawl-search', 'firecrawl-scrape', 'firecrawl-research-index', 'firecrawl-developer-index')})
        for item in items:
            self.assertEqual(item['type'], 'skill')
            self.assertEqual(item['generator'], 'firecrawl-skills-import')
            self.assertEqual(item['permissions'], [])
            self.assertEqual(item['provenance']['repository'], 'https://github.com/firecrawl/skills')
            self.assertRegex(item['provenance']['commit'], '^[0-9a-f]{40}$')
            self.assertEqual(item['provenance']['license'], 'ISC')
            self.assertEqual(source_hash(item['source']), item['provenance']['sha256'])
            self.assertIn('Permission to use, copy, modify', item['provenance']['license_text'])

    def test_tampering_and_wrong_provenance_rejected(self):
        for change in ('tamper', 'repository'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / 'firecrawl-skills'
                shutil.copytree(FIRECRAWL_SKILLS_BUNDLE_DIR, root)
                if change == 'tamper':
                    (root / 'skills/firecrawl-search/SKILL.md').write_text('changed')
                else:
                    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
                    manifest['repository'] = 'https://example.com/other'
                    (root / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    load_firecrawl_skills_bundle(root)

class FirecrawlSkillsForgeRouteTests(unittest.TestCase):
    """`POST /forge/import/firecrawl-skills` eseguito davvero, non solo letto nel sorgente."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = Flask(__name__)
        app.testing = True
        self.ns = dict(globals(), app=app, FORGE_DIR=self.tmp.name, FORGE_ADMIN_TOKEN='test-token', _forge_lock=threading.Lock(), _FORGE_TYPES={'tool', 'skill', 'patch'}, _FORGE_STATES={'draft', 'review', 'approved', 'disabled'}, load_firecrawl_skills_bundle=load_firecrawl_skills_bundle, FIRECRAWL_SKILLS_BUNDLE_DIR=FIRECRAWL_SKILLS_BUNDLE_DIR, push_log=lambda *args, **kwargs: None)
        self.ns['_bp'] = Blueprint('forge-firecrawl_skills', __name__)
        source = Path(__file__).parents[1] / 'control-plane/cp/forge.py'
        names = {'_forge_path', '_forge_write', '_forge_authorized', '_forge_validate', '_forge_read_skill', 'forge_import_firecrawl_skills'}
        nodes = [node for node in ast.parse(source.read_text(encoding='utf-8')).body if isinstance(node, ast.FunctionDef) and node.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), self.ns)
        app.register_blueprint(self.ns['_bp'])
        self.client = app.test_client()
        self.headers = {'X-Hyperspace-Forge-Token': 'test-token'}

    def test_import_requires_token_and_is_idempotent(self):
        self.assertEqual(self.client.post('/forge/import/firecrawl-skills', json={}).status_code, 403)
        response = self.client.post('/forge/import/firecrawl-skills', headers=self.headers, json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json['artifacts']), 4)
        entry = response.json['artifacts'][0]
        self.assertTrue(entry['created'])
        item = self.ns['_forge_read_skill'](entry['id'])
        self.assertEqual(item['status'], 'draft')
        self.assertEqual(item['type'], 'skill')
        self.assertTrue(item['validation']['valid'])
        again = self.client.post('/forge/import/firecrawl-skills', headers=self.headers, json={})
        self.assertFalse(any((item['created'] for item in again.json['artifacts'])))
