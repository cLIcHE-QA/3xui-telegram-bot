# GitHub Actions storage secret audit

Этот audit дополняет `docs/GIT_HISTORY_SECRET_AUDIT.md` и закрывает retained Actions storage часть A-010/#243.

## Что проверяется

Manual workflow `Actions storage secret audit`:

- перечисляет retained GitHub Actions runs;
- скачивает retained job log archives через GitHub API;
- перечисляет и скачивает retained Actions artifacts;
- проверяет тексты и filenames теми же safe detectors, что history audit;
- сохраняет только detector/fingerprint/source metadata;
- пытается получить только **имена** repository Actions Secrets и Variables, но никогда не secret values;
- отдельно сравнивает текущие и исторические workflow references к `secrets.*` / `vars.*`.

## Safety

- raw logs и artifacts не загружаются обратно как audit evidence;
- raw secret values не печатаются scanner'ом;
- report содержит только fingerprint и ограниченные source identifiers;
- download redirect на blob storage выполняется без forwarding GitHub token;
- если log/artifact недоступен, oversized или unreadable, audit помечает coverage incomplete и завершается non-zero.

## Запуск

После merge:

1. GitHub → Actions → **Actions storage secret audit**.
2. Run workflow на `main`.
3. Для acceptance фиксируются exact SHA, workflow run ID, sanitized report и coverage status.

Repository Actions Secrets/Variables по именам также можно проверить вручную в:

`Settings → Secrets and variables → Actions`.

До полного coverage retained logs/artifacts и disposition всех findings #243 не закрывается.
