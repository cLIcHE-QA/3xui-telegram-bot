# A-008 / #241 — supply-chain closure — 2026-10-06

Статус: **PASS / Closed after merge**.

## Exact main evidence

Supply-chain audit автоматически выполнен после merge PR #274 на exact `main` SHA:

`80a989d0342ffcbb097caf3184d7d5d118ed68b4`

Evidence:

- workflow: `Supply-chain audit`;
- run ID: `37507349749`;
- conclusion: `success`;
- artifact ID: `11432761040`;
- artifact name: `supply-chain-audit-80a989d0342ffcbb097caf3184d7d5d118ed68b4`;
- artifact digest: `sha256:32bffc6ef9bd08d035a044ea7bcd6151276c407a5f455a0e0f4d1289805a2d86`.

## Immutable baseline

- Python dependency graph: `requirements.lock` with exact versions and SHA-256 hashes;
- runtime install: `pip --require-hashes`;
- base image: `python:3.12-slim@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f`;
- third-party GitHub Actions pinned to reviewed full commit SHA;
- scanner: Trivy v0.75.0;
- Trivy Linux-64bit asset SHA-256: `c6e65abddb348e25f10549df887045629cf28cc72453cd1c63acb717316b3f3f`;
- artifacts include vulnerability reports, license inventories, CycloneDX SBOM и metadata exact source SHA.

## Vulnerability disposition

Python dependency findings after remediation:

- HIGH: 0;
- CRITICAL: 0.

В ходе implementation scanner обнаружил 3 actionable HIGH в `cryptography 46.0.7`; dependency обновлён до `cryptography 50.0.2`, после чего Python HIGH/CRITICAL findings стали 0.

Container/base-image report сохраняет vendor-unfixed/fix-deferred Debian findings. Blocking gate использует `--ignore-unfixed`: полный JSON сохраняет все findings, а CI блокирует HIGH/CRITICAL, для которых доступен fix. На closure run actionable container HIGH/CRITICAL = 0.

## License disposition

Project license выбран отдельно в A-009/#242: Apache License 2.0.

Compatibility review зафиксирован в:

`docs/audits/v4-a009-license-review-2026-10-06.md`

Third-party BSD/MIT notices сохранены; MPL-2.0 `certifi` остаётся отдельно лицензированным dependency material.

## Subsequent main change

После exact-main scanner run PR #275 добавил Apache-2.0 licensing/documentation и regression test. Diff `80a989d...9bb2dd3` изменяет только:

- `LICENSE`;
- `README.md`;
- `THIRD_PARTY_NOTICES.md`;
- license audit documentation;
- final audit documentation;
- project-license regression test.

`requirements.txt`, `requirements.lock`, `Dockerfile`, `supply-chain/**` и `.github/workflows/**` не менялись. Поэтому audited supply-chain inputs и scanner disposition остаются применимыми к текущему `main`.

## Closure

A-008/#241 считается закрытым: reproducible dependency graph, immutable base/Actions inputs, vulnerability/license scan, SBOM/container scan, documented update process и exact-main artifact evidence присутствуют.
