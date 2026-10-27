# Supply-chain baseline

Этот документ задаёт канонический reproducible dependency/container/Actions contract проекта; source/build evidence не подтверждает deployment или runtime acceptance.

## Immutable runtime inputs

Python runtime dependencies устанавливаются только из `requirements.lock`:

~~~bash
python -m pip install --require-hashes -r requirements.lock
~~~

`requirements.txt` остаётся human-maintained direct dependency intent. `requirements.lock` содержит полный resolved graph с exact versions и SHA-256 hashes.

Container base закреплён одновременно human-readable tag и immutable digest:

~~~text
python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
~~~

Каноническое значение также хранится в `supply-chain/base-image.txt`.

Все third-party GitHub Actions в repository workflows используют full 40-character commit SHA. Reviewed pins:

- `actions/checkout` → `11d5960a326750d5838078e36cf38b85af677262`
- `actions/setup-python` → `a26af69be951a213d495a4c3e4e4022e16d87065`
- `actions/upload-artifact` → `ea165f8d65b6e75b540449e92b4886f43607fa02`

## Audit scanner

Canonical scanner: Trivy `v0.75.0`, Linux x86_64 archive SHA-256:

~~~text
c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f
~~~

Workflow `.github/workflows/supply-chain-audit.yml` скачивает exact release asset, проверяет checksum до исполнения и сохраняет:

- Python/filesystem vulnerability JSON;
- Python/filesystem license JSON;
- container vulnerability JSON;
- container license JSON;
- CycloneDX container SBOM;
- metadata JSON с source SHA, base image digest, lock SHA-256, scanner version/checksum и Action pins.

HIGH/CRITICAL vulnerability findings блокируют audit job. License inventory сохраняется как evidence, но окончательная third-party compatibility disposition зависит от решения по project license в A-009/#242.

## Обновление Python dependencies

### Минимальный DNS dependency floor

`dnspython>=2.9,<3`, exact lock `2.9.0`: исправленная upstream версия для публичного [CVE-2026-114605 / GHSA-45c3-73f7-pv4m](https://github.com/rthalley/dnspython/security/advisories/GHSA-45c3-73f7-pv4m). Untrusted DNS wire data относится к отдельному parsing trust boundary; успешный mock DNS/HTTP test не отменяет actionable scanner finding. Python>=3.11 поддерживается в уже закреплённом runtime3.12, менять base image/другие pins ради этого обновления не нужно.

Для этого floor lock сгенерирован canonical pip-tools7.6.1 в чистом CPython3.12; изменён только dnspython block, оба SHA-256 universal wheel/sdist сверены с official PyPI metadata, `--require-hashes` install и `pip check` в отдельном чистом runtime обязательны. Не возвращать vulnerable pin и не скрывать finding CVE waiver. Исторический source/image FAIL40588425118 сохраняется в dated audit; release gate снимается только новым audit PASS на исправленном source SHA, с review licenses/SBOM.

В #966 source/build PASS отделён от собственного отложенного runtime outcome: после отдельно разрешённого deployment read-only installed package/image tag/SHA и безопасный DNS/API compatibility/health; exploit/DoS load и новые опасные mutations не нужны. До этого #966 OPEN/keep_open, старые опубликованные tags не меняются. Наличие патча в lock не доказывает применённое обновление на VPS.

### Каноническая процедура

Обновление выполняется отдельным PR.

1. Измени direct ranges в `requirements.txt`.
2. Используй clean CPython 3.12 environment.
3. Установи exact lock tool:
   `python -m pip install pip-tools==7.6.1`.
4. Сгенерируй lock:
   `python -m piptools compile --resolver=backtracking --generate-hashes --strip-extras --output-file requirements.lock requirements.txt`.
5. Проверь:
   `python -m pip install --require-hashes -r requirements.lock && python -m pip check`.
6. Запусти весь CI и Supply-chain audit.
7. Review dependency diff, vulnerabilities и license inventory до merge.

Не редактируй transitive versions/hashes вручную без отдельного documented incident reason.

## Обновление base image

1. Получи текущий manifest digest официального `python:3.12-slim`.
2. Review upstream image/release change.
3. Одним PR обнови digest в `Dockerfile` и `supply-chain/base-image.txt`.
4. Build image и запусти Supply-chain audit.
5. Review OS/package vulnerability diff и SBOM diff.

Tag без digest запрещён.

## Обновление GitHub Actions

Mutable refs вида `@v4`, `@main` или tag-only refs запрещены.

При upgrade:

1. выбери reviewed upstream release/tag;
2. resolve tag до exact commit SHA;
3. review upstream release notes и commit provenance;
4. замени full SHA во всех workflows;
5. оставь major tag только как комментарий;
6. запусти CI и Supply-chain audit.

## Release/publication gate

Перед public publication final audited source SHA должен иметь успешный Supply-chain audit artifact. В audit evidence фиксируются run ID, artifact ID/digest, source SHA и disposition всех HIGH/CRITICAL findings. License compatibility закрывается только после A-009/#242.
