from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from db_migrations import CURRENT_SCHEMA_VERSION
from version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def replace_required(source: str, old: str, new: str) -> str:
    """Негативная фикстура обязана изменить единственное совпадение."""
    if source.count(old) != 1:
        raise AssertionError(f"expected one anchor: {old!r}")
    updated = source.replace(old, new, 1)
    if updated == source:
        raise AssertionError("negative fixture did not change input")
    return updated


def current_status_fragments(document: str) -> tuple[str, str]:
    """Сравниваем только каноническую текущую строку, а не исторические checkpoints."""
    lines = [line for line in document.splitlines() if line.startswith("**Published:** immutable ")]
    if len(lines) != 1:
        raise ValueError("ожидается ровно одна текущая строка Published")
    line = lines[0]
    parts = re.split(r"\*\*(Deployed|Accepted):\*\*", line)
    if len(parts) != 5 or not parts[2].strip() or not parts[4].strip():
        raise ValueError("текущая сводка требует отдельные Deployed и Accepted")
    deployed, accepted = parts[2].strip(), parts[4].strip()
    if not re.search(r"`v\d+\.\d+\.\d+[^\x60]*`", deployed):
        raise ValueError("текущий Deployed должен содержать версию")
    if not re.search(r"SHA `[0-9a-f]{40}`", deployed):
        raise ValueError("текущий Deployed должен содержать полный SHA")
    if "operator-reported" not in deployed and "independent" not in deployed:
        raise ValueError("текущий Deployed должен указывать provenance")
    return deployed, accepted


def status_projection_errors(readme: str, roadmap: str) -> list[str]:
    try:
        readme_state = current_status_fragments(readme)
        roadmap_state = current_status_fragments(roadmap)
    except ValueError as error:
        return [str(error)]
    return [name + " README/Roadmap mismatch"
            for name, left, right in zip(("Deployed", "Accepted"), readme_state, roadmap_state)
            if left != right]



def current_release_claim_errors(roadmap: str, docs: dict[str, str]) -> list[str]:
    """Проверка только явно текущих assertions; датированные исторические audits не переписывать."""
    canonical = next((l for l in roadmap.splitlines() if l.startswith("**Published:** immutable ")), "")
    published = re.search(r"`(v\d+\.\d+\.\d+[^\x60]*)`", canonical)
    deployed = re.search(r"\*\*Deployed:\*\*[^\n]*?`(v\d+\.\d+\.\d+[^\x60]*)`", canonical)
    if not published or not deployed:
        return ["Roadmap: missing canonical release versions"]
    expected_published, expected_deployed = published.group(1), deployed.group(1)
    issues: list[str] = []
    client = docs["docs/CLIENT_SETUP.md"]
    header = next((l for l in client.splitlines() if "**Текущий статус контролируемого пилота:**" in l), "")
    if not header or f"Published `{expected_published}`" not in header or f"Deployed operator-reported `{expected_deployed}`" not in header:
        issues.append("CLIENT_SETUP current Published/Deployed drift")
    ui = docs["docs/UI_STYLE.md"]
    if re.search(r"^\*\*C3/#743 — fix candidate", ui, re.M):
        issues.append("UI_STYLE obsolete candidate as current")
    schema = docs["docs/SQLITE_MIGRATIONS.md"]
    if "Исторический Published, текущий operator-reported Deployed" in schema:
        issues.append("SQLITE_MIGRATIONS obsolete deployed baseline")
    readme = docs["README.md"]
    if re.search(r"Актуальный controlled canary `rc\.\d+", readme):
        issues.append("README obsolete current canary")
    changelog = docs["CHANGELOG.md"]
    if f"## Планируемый {expected_published} — до выпуска" in changelog:
        issues.append("CHANGELOG published version presented as unreleased")
    return issues

class LivingDocsSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(
            (ROOT / "docs" / "live-docs.json").read_text(encoding="utf-8")
        )

    def test_contract_has_unique_valid_rules_and_existing_documents(self):
        self.assertEqual(self.contract["schema"], 1)

        living_documents = self.contract["living_documents"]
        self.assertEqual(len(living_documents), len(set(living_documents)))
        for path in living_documents:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file(), path)

        rule_ids = [rule["id"] for rule in self.contract["rules"]]
        self.assertEqual(len(rule_ids), len(set(rule_ids)))
        for rule in self.contract["rules"]:
            with self.subTest(rule=rule["id"]):
                self.assertIn(rule["mode"], {"require_all", "review"})
                self.assertTrue(rule["triggers"])
                self.assertTrue(rule["documents"])
                for path in rule["documents"]:
                    self.assertIn(path, living_documents)
                if rule["mode"] == "review":
                    self.assertTrue(rule.get("waiver"))

    def test_current_release_version_is_reflected_in_living_docs(self):
        version = APP_VERSION
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")

        self.assertTrue(readme.startswith(f"# Telegram-бот для 3x-ui v{version}"))
        self.assertIn(f"## v{version} ", changelog)
        self.assertIn(f"Guide ориентирован на release v{version}.", admin_setup)
        procedures = (ROOT / "docs/ADMIN_SETUP_PROCEDURES.md").read_text(encoding="utf-8")
        self.assertIn(f"git checkout --detach v{version}", procedures)

    def test_current_sqlite_schema_version_is_documented(self):
        migration_doc = (ROOT / "docs" / "SQLITE_MIGRATIONS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f"schema **v{CURRENT_SCHEMA_VERSION}**",
            migration_doc,
        )

    def test_current_3xui_contract_is_reflected_in_living_docs(self):
        manifest = json.loads(
            (ROOT / "contracts" / "3xui" / "contract.json").read_text(
                encoding="utf-8"
            )
        )
        version = manifest["supported_3xui_version"]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(
            encoding="utf-8"
        )
        contract_doc = (ROOT / "docs" / "3XUI_OPENAPI_CONTRACT.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(f"- 3x-ui: `v{version}`;", readme)
        self.assertIn(f"Pinned supported 3x-ui для текущего `main`: `v{version}`",
                      (ROOT / "docs/ADMIN_SETUP_PROCEDURES.md").read_text(encoding="utf-8"))
        self.assertIn(f"- 3x-ui: `v{version}`;", contract_doc)
        declared_count = re.findall(r"Текущий manifest содержит \*\*(\d+)\*\* endpoints", contract_doc)
        self.assertEqual(len(declared_count), 1, "Manifest endpoint count must appear exactly once")
        self.assertEqual(int(declared_count[0]), len(manifest["endpoints"]))
        vendored = ROOT / manifest["vendored_schema"]
        self.assertTrue(vendored.is_file())
        # Upstream v3.10.0 и v3.10.2 используют один immutable blob.
        # Проверяем SHA содержимого, а не имя каталога с vendored JSON.
        import hashlib
        payload = vendored.read_bytes()
        raw_blob = b"blob " + str(len(payload)).encode() + b"\0" + payload
        self.assertEqual(
            hashlib.sha1(raw_blob).hexdigest(),
            manifest["upstream"]["schema_blob_sha"],
        )

    def test_3xui_living_docs_trigger_contract(self):
        rules = {rule["id"]: rule for rule in self.contract["rules"]}
        self.assertEqual(rules["3xui-openapi-contract"]["mode"], "require_all")
        self.assertEqual(set(rules["3xui-openapi-contract"]["triggers"]), {"contracts/3xui/contract.json", "contracts/3xui/**/openapi.json"})
        self.assertEqual(rules["3xui-openapi-contract"]["documents"], ["docs/3XUI_OPENAPI_CONTRACT.md"])
        self.assertEqual(rules["3xui-client-api"]["mode"], "review")
        self.assertEqual(set(rules["3xui-client-api"]["triggers"]), {"xui.py", "version_api.py"})

    def test_public_security_reporting_is_current(self):
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("Private Vulnerability Reporting is enabled", security)
        self.assertIn("Report a vulnerability", security)
        self.assertIn("public repository", security)
        self.assertIn("Limited prerelease security support", security)
        self.assertIn("Latest published v5.0.0-rc.N (controlled pilot)", security)
        self.assertIn("do not require reproduction on v4", security)
        self.assertIn("Private Vulnerability Reporting", security)
        self.assertIn("new immutable published RC", security)

    def test_git_and_release_docs_record_current_rulesets(self):
        git_workflow = (ROOT / "docs" / "GIT_WORKFLOW.md").read_text(
            encoding="utf-8"
        )
        releases = (ROOT / "docs" / "RELEASES.md").read_text(encoding="utf-8")
        expected = self.contract["repository_state"]

        for document in (git_workflow, releases):
            self.assertIn(expected["branch_ruleset"]["name"], document)
            self.assertIn(expected["tag_ruleset"]["name"], document)

        self.assertIn("refs/tags/v*", git_workflow)
        self.assertIn("refs/tags/v*", releases)

    def test_roadmap_has_current_next_product_track(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        self.assertIn("## Актуальная сводка проекта", roadmap)
        self.assertIn("## Реестр acceptance-gates", roadmap)
        self.assertIn("🟠 Опубликовано; acceptance отложен", roadmap)
        self.assertIn("v" + APP_VERSION, roadmap)
        self.assertIn("NOT PASS", roadmap)
        self.assertIn("## Активный Issue-реестр (machine-checked)", roadmap)
        self.assertIn("⬜ Запланировано", roadmap)

    def test_current_release_status_in_readme_and_roadmap(self):
        """APP_VERSION при release-prep может опережать immutable Published tag.

        GitHub Published tag дополнительно сверяет read-only governance CI.
        """
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        candidate = "v" + APP_VERSION
        readme_line = next((
            line for line in readme.splitlines()
            if line.startswith("**Published:** immutable [`")
        ), None)
        roadmap_line = next((
            line for line in roadmap.splitlines()
            if line.startswith("**Published:** immutable [Тег `")
        ), None)
        self.assertIsNotNone(readme_line)
        self.assertIsNotNone(roadmap_line)
        published_readme = readme_line.split("`")[1]
        published_roadmap = roadmap_line.split("`")[1]
        self.assertTrue(published_readme.startswith("v"))
        self.assertEqual(published_readme, published_roadmap)
        self.assertIn(f"## {candidate} ", changelog)
        self.assertIn(candidate, readme)
        self.assertIn(candidate, roadmap)
        for document in (readme, roadmap):
            self.assertIn("**Deployed:**", document)
            self.assertIn("**Accepted:**", document)
        if published_readme != candidate:
            self.assertIn("release-prep", readme.lower())
            self.assertNotIn(f"**Published:** immutable [`{candidate}`]", readme)
            self.assertNotIn(f"**Published:** immutable [Тег `{candidate}`]", roadmap)
            self.assertIn("PENDING", roadmap)
        self.assertEqual(status_projection_errors(readme, roadmap), [])
        self.assertNotIn("Текущий опубликованный `rc.7`", readme)



    def test_deployment_status_projection_negative_cases(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        self.assertEqual(status_projection_errors(readme, roadmap), [])
        deployed_match = re.search(r"\*\*Deployed:\*\* operator-reported `(v[^`]+)`", roadmap)
        self.assertIsNotNone(deployed_match)
        deployed_tag = deployed_match.group(1)
        self.assertIn("Deployed README/Roadmap mismatch", status_projection_errors(
            replace_required(readme, f"operator-reported `{deployed_tag}`", "operator-reported `v0.0.0`"), roadmap))
        self.assertIn("Deployed README/Roadmap mismatch", status_projection_errors(
            replace_required(readme, "health OK; independent VPS", "health FAIL; independent VPS"), roadmap))
        self.assertIn("Deployed README/Roadmap mismatch", status_projection_errors(
            replace_required(readme, f"operator-reported `{deployed_tag}`", f"independent `{deployed_tag}`"), roadmap))
        self.assertIn("Accepted README/Roadmap mismatch", status_projection_errors(
            replace_required(readme, "**Accepted:**", "**Accepted:** INCONSISTENT "), roadmap))
        self.assertTrue(status_projection_errors(replace_required(readme, "**Accepted:**", "**Acceptance:**"), roadmap))
        # Исторические старые версии не относятся к текущей строке.
        self.assertEqual(status_projection_errors(readme + "\\nИстория: Deployed rc.16.4", roadmap), [])


    def test_current_setup_and_roadmap_do_not_reintroduce_stale_baselines(self):
        """Недатированные current-state блоки не должны иметь вторую release-истину."""
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        setup = (ROOT / "docs/ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertEqual(self._current_block_errors(roadmap, setup), [])

    @staticmethod
    def _current_block_errors(roadmap: str, setup: str) -> list[str]:
        """Область проверки — только явно названные текущие блоки, не historical audits."""
        errors = []
        current = roadmap.split("## Текущий этап:", 1)
        if len(current) != 2:
            return ["отсутствует текущий этап Roadmap"]
        stage = current[1].split("## Реестр acceptance-gates", 1)[0]
        if "Актуальные Published/Deployed/Accepted" not in stage:
            errors.append("текущий этап должен ссылаться на канонические статусы")
        # Дублирование устаревающего snapshot запрещено даже при совпадении сегодня.
        if re.search(r"(?:Published immutable tag|Deployed `?rc\\.\\d+)", stage):
            errors.append("в текущем этапе дублируется release/deployed baseline")
        if "**Текущая незавершённая работа:" in roadmap:
            errors.append("обнаружена параллельная текущая сводка")
        intro = setup.split("## Перед началом:", 1)[0]
        guide = next((line for line in setup.splitlines()
                      if "Guide ориентирован на release " in line), "")
        if "Roadmap](ROADMAP.md)" not in intro or "Roadmap](ROADMAP.md)" not in guide:
            errors.append("Admin Setup должен ссылаться на канонический Roadmap")
        if re.search(r"(?:Действующий published|Действующий Published|Published `v\\d|published `rc\\.|deployed `rc\\.)", intro):
            errors.append("Admin Setup дублирует/устарел текущий baseline")
        if re.search(r"Published `v\\d|\\*\\*Deployed:\\*\\*", guide):
            errors.append("Admin Setup guide дублирует Published/Deployed")
        return errors

    def test_current_block_negative_regressions(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        setup = (ROOT / "docs/ADMIN_SETUP.md").read_text(encoding="utf-8")
        self.assertTrue(self._current_block_errors(roadmap.replace(
            "Актуальные Published/Deployed/Accepted", "Published immutable tag `v5.0.0-rc.15`", 1), setup))
        self.assertTrue(self._current_block_errors(roadmap + "\\n**Текущая незавершённая работа:** rc.15", setup))
        self.assertTrue(self._current_block_errors(roadmap, replace_required(
            setup, "**Текущий Published/Deployed/Accepted status:**",
            "Published `v0.0.0`; **Deployed:** rc.0")))
        self.assertTrue(self._current_block_errors(roadmap, replace_required(
            setup, "**Текущий Published/Deployed/Accepted status:**",
            "Published `v0.0.0`; **Deployed:** rc.0")))


    def test_cross_document_current_release_claims(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        documents = {p: (ROOT / p).read_text(encoding="utf-8") for p in (
            "docs/CLIENT_SETUP.md", "docs/UI_STYLE.md",
            "docs/SQLITE_MIGRATIONS.md", "README.md", "CHANGELOG.md")}
        self.assertEqual(current_release_claim_errors(roadmap, documents), [])

    def test_cross_document_stale_claim_regressions(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        docs = {p: (ROOT / p).read_text(encoding="utf-8") for p in (
            "docs/CLIENT_SETUP.md", "docs/UI_STYLE.md",
            "docs/SQLITE_MIGRATIONS.md", "README.md", "CHANGELOG.md")}
        old = dict(docs)
        published_line = next((line for line in roadmap.splitlines()
                               if line.startswith("**Published:** immutable ")), "")
        published_match = re.search(r"`(v\d+\.\d+\.\d+(?:-rc\.\d+(?:\.\d+)?)?)`", published_line)
        self.assertIsNotNone(published_match)
        current_tag = published_match.group(1)
        self.assertIn(f"Published `{current_tag}`", old["docs/CLIENT_SETUP.md"])
        old["docs/CLIENT_SETUP.md"] = old["docs/CLIENT_SETUP.md"].replace(
            f"Published `{current_tag}`", "Published `v0.0.0`", 1)
        self.assertTrue(current_release_claim_errors(roadmap, old))
        old = dict(docs)
        old["docs/UI_STYLE.md"] = replace_required(
            old["docs/UI_STYLE.md"], "## Исторические UI и acceptance checkpoints",
            "**C3/#743 — fix candidate \u2014 нынешний статус**\n\n## Исторические UI и acceptance checkpoints")
        self.assertTrue(current_release_claim_errors(roadmap, old))
        old = dict(docs)
        old["CHANGELOG.md"] = f"## Планируемый {current_tag} — до выпуска\n\n" + old["CHANGELOG.md"]
        self.assertTrue(current_release_claim_errors(roadmap, old))

    def test_roadmap_active_issues_have_russian_explanations(self):
        roadmap = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        register = roadmap.split("## Активный Issue-реестр (machine-checked)", 1)[1].split("## Завершённые этапы", 1)[0]
        self.assertNotIn("Issue criteria", register)
        self.assertNotIn("implementation PENDING", register)
        self.assertNotIn("(scope)", register)

    def test_required_ci_reconciles_roadmap_with_github(self):
        """OPEN Issues и Published сверяются с GitHub в обязательном CI."""
        workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        living = (ROOT / "docs/LIVING_DOCS.md").read_text(encoding="utf-8")
        self.assertIn("  issues: read", workflow)
        self.assertIn(
            'python3 scripts/check-roadmap-github.py --repository "$GITHUB_REPOSITORY"',
            workflow,
        )
        self.assertIn("обязательном PR CI", living)

    def test_roadmap_registry_must_be_contiguous(self):
        import importlib.util
        from tempfile import TemporaryDirectory
        spec = importlib.util.spec_from_file_location(
            "roadmap_registry_guard", ROOT / "scripts/check-roadmap-governance.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
        # Проверяем динамически вторую строку: первая строка таблицы не
        # выявляет разрыв реестра; закрытие Issue не ломает этот тест.
        open_rows = module.roadmap_rows(ROOT)
        self.assertGreaterEqual(len(open_rows), 2)
        anchor = f"| [#{list(open_rows)[1]}]"
        self.assertIn("\n" + anchor, source)
        with TemporaryDirectory() as folder:
            temp_root = Path(folder)
            (temp_root / "docs").mkdir()
            (temp_root / "docs/ROADMAP.md").write_text(
                source.replace("\n" + anchor, "\n\n" + anchor, 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "contiguous"):
                module.roadmap_rows(temp_root)

    def test_roadmap_archive_is_lossless(self):
        import importlib.util
        path = ROOT / "scripts" / "check-roadmap-structure.py"
        spec = importlib.util.spec_from_file_location("check_roadmap_structure", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.check(ROOT)

    def test_roadmap_narrative_has_russian_language_guard(self):
        """Reject new long English-only explanations, ignoring technical literals."""
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        fence = False
        violations = []
        for number, original in enumerate(roadmap.splitlines(), 1):
            if original.lstrip().startswith(("```", "~~~")):
                fence = not fence
                continue
            if fence:
                continue
            prose = re.sub(r"`[^`]*`", "", original)
            prose = re.sub(r"\]\([^)]+\)", "]", prose)
            prose = re.sub(r"https?://\S+", "", prose)
            latin = len(re.findall(r"[A-Za-z]", prose))
            cyrillic = len(re.findall(r"[А-Яа-яЁё]", prose))
            # English-only explanatory blocks are not valid Russian docs.
            # Short API/CI labels, technical identifiers and exact source
            # fragments are allowed and must never be silently rewritten.
            if latin >= 90 and cyrillic == 0:
                violations.append(number)
        self.assertEqual(
            violations, [],
            f"Русскоязычный Roadmap: длинная английская проза, строки {violations}",
        )

    def test_roadmap_status_contract_matches_workflow_and_pr_template(self):
        roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
        workflow = (ROOT / "docs" / "GIT_WORKFLOW.md").read_text(
            encoding="utf-8"
        )
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        pr_template = (ROOT / ".github" / "pull_request_template.md").read_text(
            encoding="utf-8"
        )

        expected = (
            "⬜ Запланировано",
            "🟡 Реализовано в main",
            "🟠 Опубликовано; acceptance отложен",
            "✅ Выполнено в vX.Y.Z",
        )
        roadmap_section = roadmap.split("## Статусы дорожной карты", 1)[1].split(
            "\n## ", 1
        )[0]
        workflow_section = workflow.split("## Ведение roadmap", 1)[1].split(
            "\n## ", 1
        )[0]
        roadmap_statuses = [
            line.split("`", 2)[1]
            for line in roadmap_section.splitlines()
            if line.startswith("- `")
        ]
        workflow_statuses = [
            line.split("`", 2)[1]
            for line in workflow_section.splitlines()
            if line.startswith("- `")
        ]
        self.assertEqual(roadmap_statuses, list(expected))
        self.assertEqual(workflow_statuses, list(expected))
        for label in expected:
            with self.subTest(status=label):
                self.assertIn(f"`{label}`", agents)

        for check_status in ("PASS", "PARTIAL", "PENDING", "FAIL", "BLOCKED"):
            self.assertIn(f"`{check_status}`", workflow_section)
        self.assertIn("## Roadmap / Acceptance impact", pr_template)
        self.assertIn("Что останется проверить", pr_template)

    def test_required_pr_checklist_gate_is_wired(self):
        workflow = (
            ROOT / ".github" / "workflows" / "pr-conventions.yml"
        ).read_text(encoding="utf-8")
        git_workflow = (
            ROOT / "docs" / "GIT_WORKFLOW.md"
        ).read_text(encoding="utf-8")
        template = (
            ROOT / ".github" / "pull_request_template.md"
        ).read_text(encoding="utf-8")

        self.assertIn("types: [opened, edited, reopened, synchronize]", workflow)
        self.assertIn("      - name: Validate PR checklist", workflow)
        self.assertIn("python3 scripts/check_pr_checklist.py", workflow)
        self.assertIn("PR_BODY:", workflow)
        self.assertIn("## Checklist", template)
        self.assertIn("Обязательный чек-лист PR перед merge", git_workflow)

    def test_v5_acceptance_and_release_scope_contract(self):
        rule_by_id = {rule["id"]: rule for rule in self.contract["rules"]}
        self.assertIn("docs/V5_PRODUCTION_ACCEPTANCE.md", self.contract["living_documents"])
        self.assertIn("v5-client-acceptance", rule_by_id)
        self.assertEqual(rule_by_id["v5-client-acceptance"]["mode"], "review")

        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        admin_setup = (ROOT / "docs" / "ADMIN_SETUP.md").read_text(encoding="utf-8")
        ui = (ROOT / "docs" / "UI_STYLE.md").read_text(encoding="utf-8")
        self.assertIn("scripts/check-release-scope.py", workflow)
        self.assertIn("docs/V5_PRODUCTION_ACCEPTANCE.md", readme)
        self.assertIn("Client Portal v5 уже реализован", readme)
        self.assertNotIn("private GitHub repository", admin_setup)
        self.assertNotIn("будущий `/start`", ui)

    def test_living_docs_are_linked_from_readme_and_agent_contract(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

        self.assertIn("docs/LIVING_DOCS.md", readme)
        self.assertIn("docs/LIVING_DOCS.md", agents)
        self.assertIn("scripts/check-living-docs.py", agents)

    def test_ci_and_scheduled_repository_state_audit_are_wired(self):
        tests_workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(
            encoding="utf-8"
        )
        state_workflow = (
            ROOT / ".github" / "workflows" / "repository-state-audit.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("scripts/check-living-docs.py", tests_workflow)
        self.assertIn("pull_request.head.sha", tests_workflow)
        self.assertIn("workflow_dispatch:", state_workflow)
        self.assertIn("schedule:", state_workflow)
        self.assertIn("scripts/check-repository-state.py", state_workflow)


if __name__ == "__main__":
    unittest.main()
