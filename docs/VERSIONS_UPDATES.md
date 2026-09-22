# Versions & Updates - v4.9.0

## Entry points and permissions

`/admin -> System -> Versions & Updates` is the shared dashboard.
Infrastructure -> Panels and Master/Node cards link to it. Navigation,
confirmation and progress use `admin_ui` and edit one message in the normal path.
This workflow saves backups locally, without sending secret archives to Telegram.

Read-only/Support/Admin/Owner may view versions. Backup preparation and installation
require Admin or Owner; permission is rechecked immediately before dispatch.
Clearing an unverified outcome requires Owner and an operation-specific typed phrase.

## Manual update sequence

1. Select a host/component. Xray tags come from that host's API with pagination.
   Select an exact tag, not the moving `latest` alias. Returned prerelease tags
   remain visible; the bot does not certify their compatibility.
2. Read the current version and verify the target and available release.
3. Create and verify a fresh backup. Master requires a complete full archive with
   valid bot/Master SQLite databases and bot.env. Any missing component blocks
   installation. Nodes require a configured direct admin connection and DB download.
4. Review previous/selected versions and the backup. Confirmation is single-use,
   bound to the administrator/chat/message and valid for five minutes after backup.
5. Recheck permissions, target identity, versions, release availability and backup
   SHA-256 before dispatch. Changed conditions block installation.
6. Send exactly one update request. Service restarts can interrupt VPN sessions.
7. Poll read-only status for up to 120 seconds. Success requires the selected
   installed version and running Xray. If the panel returns an updater `runId`,
   only that exact successful run is accepted; stale runs do not count.
8. Record the outcome in existing `job_runs` and `audit_log`; no schema migration.

The Xray install request has a 180-second HTTP deadline, the panel update start
request 90 seconds. These are not promises of actual installation duration.
A timeout does not establish that the remote operation failed.

## Uncertainty and restart

There are no automatic updates, automatic retries of mutation requests or automatic
rollback. A lost response can still be followed by successful read-only verification.
Otherwise the operation remains `unconfirmed`, its job is `unknown`, and new version
updates on the same target are blocked.

The secret-free journal lives beside the bot DB in `updates/target-*.json`.
Atomic writes and per-target advisory file locks protect this workflow across
local processes. Restart does not replay an in-flight update. Open the operation
status and use **Verify result (no retry)**. If the result remains unknown, inspect
the actual server/updater first. Only then may Owner type `UNLOCK <operation nonce>`.
This clears the local block without retrying, rolling back or asserting success.

Do not run updates, restarts, restore or configuration changes through other tools
while an update is active. This lock does not control external panel administrators,
CLI commands or the pre-existing restore workflow. A changed node endpoint, token
or name invalidates prepared confirmations.

## Nodes and backups

Discovery/telemetry still comes from Master. Mutations require an enabled, online,
direct (non-transitive) node and the existing configuration:

```env
NODE_BACKUP_TARGETS=FI
NODE_BACKUP_FI_NODE_NAME=Finland
NODE_BACKUP_FI_PANEL_URL=https://fi-panel.example.com/basepath
NODE_BACKUP_FI_API_TOKEN=replace_with_dedicated_admin_scope_token
NODE_BACKUP_FI_VERIFY_TLS=true
```

The dedicated connection is reused for versions, DB backup and the host update API.
No new token is requested in the UI. Old `updatepanel:run` buttons redirect to the
new screen and cannot bypass backup/confirmation. Nodes without a direct token
remain visible through telemetry but cannot be updated from this workflow.

Rescue copies are private files below `BACKUP_DIR/rescue/updates/<target>/`, outside
ordinary full-backup retention. Cancellation keeps them. Preserve appropriate copies
before manual cleanup; they contain credentials and must not be committed or attached
to public issues. The update journal contains metadata/checksums, not token values.

SQLite backups undergo `PRAGMA quick_check`. PostgreSQL custom `.dump` files receive
only a format-header sanity check and SHA-256 verification, NOT a pg_restore rehearsal.
Database backups do not contain previous Xray/3x-ui binaries. Recovery may require
reinstalling a compatible binary separately and restoring data through the existing
Disaster Recovery workflow. Master PostgreSQL-only deployments are not supported by
this release's local SQLite full-backup gate.

## API contracts and limitations

Checked against MHSanaei/3x-ui commit `95f19b192f477b59cc368dcb7751bcf2e0180e5b`:

- [Server controller](https://github.com/MHSanaei/3x-ui/blob/95f19b192f477b59cc368dcb7751bcf2e0180e5b/internal/web/controller/server.go)
- [Panel update service](https://github.com/MHSanaei/3x-ui/blob/95f19b192f477b59cc368dcb7751bcf2e0180e5b/internal/web/service/panel/panel.go)

`GET /panel/api/server/getPanelUpdateInfo` supplies panel versions.
`GET /panel/api/server/getXrayVersion` supplies Xray tags.
`POST /panel/api/server/installXray/<exact tag>` installs the core.
`POST /panel/api/server/updatePanel` receives form-encoded `dev=false`.
`GET /panel/api/server/getUpdateStatus` supplies a string runId and outcome.

The saved update channel is never changed. On a dev-channel panel the bot queries
GitHub's official latest stable release without sending panel credentials.
The native stable updater resolves latest at execution time; it cannot pin a panel
version through this API. A release appearing during installation can therefore
produce an unconfirmed version mismatch, never a fabricated success.

Missing endpoints, unknown versions or failed release lookups are reported.
The self-updater remains subject to 3x-ui's OS/deployment restrictions. Docker-based
panels may need their image updated through deployment tooling instead.
Tests use fake local APIs; no live panel is modified by tests.

## Deployment and tests

Merge the reviewed PR before updating the production Git checkout. Preserve `.env`
and `data/`, and verify a usable recovery copy before deployment:

```bash
git pull --ff-only
docker compose up -d --build
docker compose logs --tail=100 bot
```

First check version display, Read-only access, no-token node behavior, cancellation
and navigation. Rehearse a real update on a non-critical target during maintenance;
verify actual VPN connectivity separately. A running process does not prove every
transport or client configuration is compatible with an upgrade/downgrade.

```bash
python -m pip install -r requirements.txt
python -m compileall -q .
python -m unittest discover -s tests -v
```

Workflow/API/backup tests use local fakes and temporary files. Integration tests
import the actual application with fake environment values and cover menus, RBAC,
legacy callbacks, backup manifests and audit/job records. Missing dependencies fail
the integration tests rather than silently skipping them. Retained PR CI has
read-only permissions and never calls production endpoints.
