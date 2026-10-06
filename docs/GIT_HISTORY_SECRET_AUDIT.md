# Git-history secret audit

Этот runbook закрывает repository-history часть A-010/#243 перед public publication.

## Safety contract

- raw secret values не публикуются в issue/PR/Actions artifact;
- Gitleaks запускается с `--redact=100`;
- raw Gitleaks JSON живёт только во временном каталоге и удаляется;
- versioned evidence содержит только rule/file/commit/line/fingerprint;
- private IP, Telegram ID и endpoint candidates сохраняются только как SHA-256 fingerprint;
- найденный реальный credential сначала rotate/revoke, и только затем решается вопрос sanitization Git history.

## Scanner baseline

Canonical runner:

~~~bash
bash scripts/run-history-secret-audit.sh /tmp/3xui-history-secret-audit
~~~

Runner использует:

- Gitleaks `v8.30.1`;
- Linux x64 release archive SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`;
- repository scanner `scripts/scan-git-history-sensitive.py`;
- sanitized reports `gitleaks-safe.json` и `history-metadata.json`.

Перед запуском нужен full clone с refs/tags:

~~~bash
git fetch --force --tags origin '+refs/heads/*:refs/remotes/origin/*'
git fsck --full
bash scripts/run-history-secret-audit.sh /tmp/3xui-history-secret-audit
~~~

## GitHub Actions evidence

Workflow `.github/workflows/history-secret-audit.yml` запускается вручную после merge audit tooling в `main`.

Он:

1. checkout с `fetch-depth: 0`;
2. fetch всех remote branches и tags;
3. запускает canonical runner;
4. публикует только sanitized reports.

Нельзя публиковать raw scanner output, если он содержит secret-bearing fields.

## Actions logs/artifacts review

Repository history scan не заменяет review GitHub Actions storage.

Перед publication отдельно проверяются retained Actions logs/artifacts:

- нет загруженных `.env`, DB, backup, private key, enrollment или credential artifacts;
- workflow logs не содержат unmasked credentials или production-specific private data;
- repository Actions secrets/variables сверяются по именам и необходимости; сами secret values не копируются в audit report;
- obsolete credentials rotate/revoke и удаляются из repository settings.

Если retained artifact/log содержит реальный secret, сначала credential считается exposed и rotate/revoke. Удаление artifact/log выполняется после rotation.

## Acceptance record

Versioned audit note фиксирует:

- exact source SHA;
- Gitleaks version + archive SHA-256;
- команды;
- sanitized finding counts;
- disposition каждого candidate без secret values;
- результат Actions logs/artifacts review;
- итог: unresolved real secrets = 0.

До выполнения scan на merged audited SHA и review Actions storage #243 остаётся open.
