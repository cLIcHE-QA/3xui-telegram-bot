from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_pr_checklist import extract_checkboxes, validate_pr_body


ROOT = Path(__file__).resolve().parents[1]
TEST_TEMPLATE = """## Что изменено

Описание.

## Проверки

- [ ] CI прошло.
- [ ] Smoke рассмотрен.

## Documentation impact

- [ ] Документы проверены.

## Roadmap / Acceptance impact

- [ ] Roadmap проверен.

## Checklist

- [ ] Заголовок проверен.
"""


class PrChecklistTests(unittest.TestCase):
    @staticmethod
    def completed(template: str = TEST_TEMPLATE) -> str:
        return template.replace("- [ ]", "- [x]")

    def test_completed_checklist_passes(self):
        self.assertEqual(validate_pr_body(self.completed(), TEST_TEMPLATE), [])

    def test_unchecked_template_item_blocks(self):
        body = self.completed().replace(
            "- [x] Smoke рассмотрен.", "- [ ] Smoke рассмотрен."
        )
        errors = validate_pr_body(body, TEST_TEMPLATE)
        self.assertTrue(any("Чекбокс" in message for message in errors), errors)

    def test_removed_template_item_blocks_even_when_others_are_checked(self):
        body = self.completed().replace("- [x] Smoke рассмотрен.\n", "")
        errors = validate_pr_body(body, TEST_TEMPLATE)
        self.assertTrue(any("Отсутствует обязательный" in e for e in errors))

    def test_empty_description_blocks(self):
        self.assertTrue(validate_pr_body("", TEST_TEMPLATE))

    def test_missing_required_section_blocks(self):
        body = self.completed().replace("## Checklist", "## Заметки")
        self.assertTrue(any("раздел" in e for e in validate_pr_body(body, TEST_TEMPLATE)))

    def test_extra_unchecked_checkbox_blocks(self):
        body = self.completed() + "\n- [ ] Необъяснимое ожидание.\n"
        self.assertTrue(any("Чекбокс" in e for e in validate_pr_body(body, TEST_TEMPLATE)))

    def test_code_fences_do_not_create_false_checkboxes(self):
        body = self.completed() + (
            "\n```markdown\n"
            "- [ ] Это только пример в документации.\n"
            "```\n"
        )
        self.assertEqual(validate_pr_body(body, TEST_TEMPLATE), [])

    def test_nested_numbered_and_uppercase_checkboxes(self):
        body = self.completed().replace(
            "- [x] CI прошло.", "  1. [X] CI прошло."
        )
        self.assertEqual(validate_pr_body(body, TEST_TEMPLATE), [])

    def test_unchecked_checkbox_in_nested_list_blocks(self):
        body = self.completed() + "\n  * [ ] Забытый пункт.\n"
        self.assertTrue(validate_pr_body(body, TEST_TEMPLATE))

    def test_missing_template_checklist_blocks(self):
        self.assertTrue(validate_pr_body(self.completed(), "## Checklist\n"))

    def test_real_template_is_self_consistent(self):
        template = (
            ROOT / ".github" / "pull_request_template.md"
        ).read_text(encoding="utf-8")
        items = extract_checkboxes(template)
        self.assertGreaterEqual(len(items), 10)
        self.assertEqual(
            validate_pr_body(self.completed(template), template), []
        )


if __name__ == "__main__":
    unittest.main()
