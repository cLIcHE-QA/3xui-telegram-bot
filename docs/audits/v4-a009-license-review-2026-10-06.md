# A-009 / #242 — project license review — 2026-10-06

Статус: **READY FOR CLOSURE ON MERGE**.

Owner decision: project-authored code публикуется по **Apache License 2.0**.

## Project license

Canonical file: `LICENSE`.

README содержит отдельный раздел License и ссылку на canonical terms.

`THIRD_PARTY_NOTICES.md` явно отделяет project-authored code от third-party materials: Apache-2.0 не заменяет upstream licenses/attribution.

## Reviewed third-party material already tracked in repository

- Cheburcheck reference/integration: BSD-3-Clause; required notice сохранён в `THIRD_PARTY_NOTICES.md`.
- PackBot behavior/reference material: MIT; required notice сохранён в `THIRD_PARTY_NOTICES.md`.
- Vendored 3x-ui OpenAPI используется как API contract snapshot; отдельного переноса project ownership на этот material не заявляется.

BSD-3-Clause и MIT не требуют relicensing project-authored code и совместимы с распространением проекта под Apache-2.0 при сохранении notices.

## Python runtime dependency license inventory

Supply-chain artifact для PR #273 содержит 36 Python license records.

Основные группы:

- Apache-2.0;
- MIT / MIT-0 / MIT-CMU;
- BSD-3-Clause;
- ISC;
- PSF-2.0;
- MPL-2.0 для `certifi`.

Scanner UNKNOWN classifications вручную сопоставлены с package metadata:

- `aiohappyeyeballs` — PSF-2.0;
- `cffi` — MIT-0;
- `Pillow` — MIT-CMU;
- `typing_extensions` — PSF-2.0;
- `qrcode` metadata одновременно содержит BSD и legacy `Other/Proprietary License` classifier; PyPI указывает фактическую лицензию как BSD.

MPL-2.0 у `certifi` является file-level reciprocal license для самого dependency material. Этот dependency остаётся отдельно лицензированным и не переводит project-authored source code под MPL.

## Base image / OS packages

Pinned `python:3.12-slim` содержит Debian packages под GPL/LGPL и другими системными лицензиями. Текущий release process проекта не публикует prebuilt container image/registry artifact: deployment собирает image локально из Dockerfile и официального base image.

Следствие:

- Apache-2.0 применим к project-authored repository source;
- licenses base-image packages не меняют project license;
- если в будущем проект начнёт распространять prebuilt container images, перед такой публикацией нужен отдельный container-distribution license/notice/source-obligation review.

## Disposition

Для текущей модели распространения source repository + local Docker build не найдено third-party condition, требующего сменить выбранную Apache-2.0 project license.

Это engineering license-compliance review для release gate, не юридическая консультация.

После merge этого change A-009/#242 может быть закрыт как выполненный.
