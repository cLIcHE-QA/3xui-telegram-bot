from __future__ import annotations
import unittest
from scripts.check_project_language import long_english, check_pr, check_diff

class ProjectLanguageTests(unittest.TestCase):
    def test_long_english_prose_rejected(self):
        self.assertTrue(long_english("This document explains how the full deployment process and corresponding security approvals should be performed by every contributor in our project."))
    def test_russian_with_technical_terms_allowed(self):
        self.assertFalse(long_english("Проверить Xray, API, Flow, inboundIds, security и GitHub Actions перед merge."))
    def test_inline_code_excluded(self):
        self.assertFalse(long_english("`ThisDocumentExplainsHowTheDeploymentProcessShouldBePerformedByEveryContributorInOurProject`"))
    def test_pr_russian(self):
        self.assertEqual(check_pr("docs: закрепить русский язык", "Все критерии проверены."), [])
        self.assertEqual(check_pr("release: v5.0.0-rc.11", ""), [])
    def test_pr_english_prose(self):
        self.assertTrue(check_pr("docs: Update all documentation conventions without prior review", ""))
    def test_changed_markdown_only(self):
        bad="+++ b/docs/ADMIN_SETUP.md\n+This document explains how the full deployment process and corresponding security approvals should be performed by every contributor in our project."
        good="+++ b/docs/ADMIN_SETUP.md\n+Проверить актуальное состояние GitHub и документацию."
        self.assertTrue(check_diff(bad))
        self.assertFalse(check_diff(good))
        self.assertFalse(check_diff("-This document explains how the full deployment process and corresponding security approvals should be performed by every contributor in our project."))
