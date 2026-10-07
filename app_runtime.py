import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher

from backup_manager import BackupManager
from config import load_settings
from db import Database
from versions_updates import versions_router
from bot_updates import bot_updates_router, reconcile_deploy_jobs
from system_backup import SystemBackupService
from subscription_proxy import SubscriptionProxy
from commerce import CommerceService
from payment_webhook import PaymentWebhookGateway
from catalog_admin import catalog_router
from admin_observability import observability_router
from business_admin import business_router
from advanced_users import advanced_users_router
from user_groups_admin import user_groups_router
from inbound_admin import inbound_admin_router
from advanced_nodes import advanced_nodes_router
from host_control_ui import host_control_router, recover_control_jobs
from fleet_operations import fleet_router, recover_fleet_operations
from audit import audit_system
from runtime_jobs import backup_lock
from logs_alerts import logs_alerts_router, alert_monitor_loop
from cheburcheck_admin import cheburcheck_router
from website_monitoring_admin import website_monitoring_router
from website_diagnostics_admin import website_diagnostics_router
from website_monitoring_runtime import website_monitoring_loop
from logging_setup import configure_logging
from disaster_recovery import disaster_recovery_router, send_boot_restore_notice
from restore_manager import RestoreManager
from offsite_backup import replicate_with_job, service_from_settings
from admin_ui import AdminPanelSessionMiddleware, AdminPrivateChatMiddleware
from node_admin import node_admin_router
from system_admin import system_admin_router
from storage_admin import storage_admin_router
from client_access import client_access_router
from admin_shell import admin_shell_router

settings = load_settings()
db = Database(settings.db_path)
backup_manager = BackupManager(settings.db_path, settings.backup_dir, settings.backup_keep)
system_backup = SystemBackupService(backup_manager, settings.node_backup_targets, settings.host_control_targets)
offsite_restore_manager = RestoreManager(settings.db_path, settings.backup_dir)
offsite_backup = service_from_settings(settings, offsite_restore_manager)
commerce_service = CommerceService(db)
payment_webhook_gateway = PaymentWebhookGateway(
    commerce_service,
    enabled=settings.payment_webhook_enabled,
    provider=settings.payment_webhook_provider,
    secret=settings.payment_webhook_secret,
)

ADMIN_ROUTERS = (
    admin_shell_router,
    node_admin_router,
    system_admin_router,
    storage_admin_router,
    versions_router,
    bot_updates_router,
    user_groups_router,
    advanced_users_router,
    advanced_nodes_router,
    host_control_router,
    fleet_router,
    inbound_admin_router,
    catalog_router,
    observability_router,
    logs_alerts_router,
    cheburcheck_router,
    website_monitoring_router,
    website_diagnostics_router,
    disaster_recovery_router,
    business_router,
)


async def _seconds_until_backup_hour() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(
        hour=settings.backup_hour_utc,
        minute=0,
        second=0,
        microsecond=0,
    )
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def automatic_backup_loop(bot: Bot):
    while True:
        await asyncio.sleep(await _seconds_until_backup_hour())
        run_id = await db.start_job_run(name="backup.daily", trigger="scheduled", actor_id=0)
        started = time.monotonic()
        try:
            async with backup_lock:
                result = await system_backup.create_full_backup()
            duration_ms = int((time.monotonic() - started) * 1000)
            await db.finish_job_run(
                run_id, status="success", duration_ms=duration_ms,
                details=f"{result.info.path.name}; {result.info.size} bytes; missing={len(result.missing)}",
            )
            await audit_system(
                db, "backup.create", target_type="backup", target_id=result.info.path.name,
                details=f"scheduled; size={result.info.size}; missing={len(result.missing)}",
            )
            logging.info(
                "Automatic backup created: %s (%d bytes)",
                result.info.path,
                result.info.size,
            )
            offsite_status, _, offsite_detail = await replicate_with_job(
                db,
                offsite_backup,
                result.info.path,
                trigger="scheduled",
                actor_id=0,
            )
            if offsite_status != "disabled":
                await audit_system(
                    db,
                    "backup.offsite.upload",
                    target_type="backup",
                    target_id=result.info.path.name,
                    details=offsite_detail,
                    success=offsite_status in {"success", "partial"},
                )
                if offsite_status == "failed":
                    logging.error("Off-site backup failed: %s", offsite_detail)
                else:
                    logging.info("Off-site backup %s: %s", offsite_status, result.info.path.name)
        except asyncio.CancelledError:
            duration_ms = int((time.monotonic() - started) * 1000)
            await db.finish_job_run(
                run_id, status="failed", duration_ms=duration_ms, details="cancelled",
            )
            raise
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            await db.finish_job_run(
                run_id, status="failed", duration_ms=duration_ms,
                details=f"{type(exc).__name__}: {exc}",
            )
            await audit_system(
                db, "backup.create", target_type="backup",
                details=f"scheduled failed: {type(exc).__name__}: {exc}", success=False,
            )
            logging.exception("Automatic backup failed")


async def _recover_deploy_after_health() -> None:
    recovered = await reconcile_deploy_jobs(wait_seconds=60)
    if recovered:
        logging.warning(
            "Recovered %d interrupted bot deployment jobs after health startup without mutation replay",
            recovered,
        )


async def main():
    configure_logging()
    await asyncio.to_thread(backup_manager._ensure_dir)
    await db.init()
    payment_recovery = await commerce_service.reconcile_recoverable_payment_events(limit=100)
    if payment_recovery["checked"]:
        logging.warning(
            "Payment event reconciliation checked=%d applied=%d still_missing=%d failed=%d",
            payment_recovery["checked"],
            payment_recovery["applied"],
            payment_recovery["still_missing"],
            payment_recovery["failed"],
        )
    recovered_deploy = await reconcile_deploy_jobs(wait_seconds=0)
    if recovered_deploy:
        logging.warning(
            "Recovered %d interrupted bot deployment jobs without mutation replay",
            recovered_deploy,
        )
    recovered_control = await recover_control_jobs()
    if recovered_control:
        logging.warning(
            "Recovered %d interrupted Host Control jobs without mutation replay",
            recovered_control,
        )
    stale_jobs = await db.fail_stale_job_runs()
    if stale_jobs:
        logging.warning("Marked %d stale job runs as failed", stale_jobs)
    recovered_fleet = await recover_fleet_operations()
    if recovered_fleet:
        logging.warning("Recovered %d interrupted fleet operations without replay", recovered_fleet)

    proxy = SubscriptionProxy(
        db=db,
        upstream_template=settings.subscription_url_template,
        public_template=settings.compat_subscription_url_template,
        verify_tls=settings.verify_tls,
        host=settings.subscription_proxy_host,
        port=settings.subscription_proxy_port,
        payment_webhook_gateway=payment_webhook_gateway,
    )
    await proxy.start()
    deploy_recovery_task = (
        asyncio.create_task(_recover_deploy_after_health())
        if settings.deploy_agent_enabled else None
    )

    bot = Bot(settings.bot_token)
    await send_boot_restore_notice(bot)
    dp = Dispatcher()
    dp.callback_query.outer_middleware(AdminPanelSessionMiddleware())
    for router in ADMIN_ROUTERS:
        router.message.outer_middleware(AdminPrivateChatMiddleware())
        router.callback_query.outer_middleware(AdminPrivateChatMiddleware())
    dp.include_router(admin_shell_router)
    dp.include_router(client_access_router)
    dp.include_router(node_admin_router)
    dp.include_router(system_admin_router)
    dp.include_router(storage_admin_router)
    dp.include_router(versions_router)
    dp.include_router(bot_updates_router)
    dp.include_router(user_groups_router)
    dp.include_router(advanced_users_router)
    dp.include_router(advanced_nodes_router)
    dp.include_router(host_control_router)
    dp.include_router(fleet_router)
    dp.include_router(inbound_admin_router)
    dp.include_router(catalog_router)
    dp.include_router(observability_router)
    dp.include_router(logs_alerts_router)
    dp.include_router(cheburcheck_router)
    dp.include_router(website_monitoring_router)
    dp.include_router(website_diagnostics_router)
    dp.include_router(disaster_recovery_router)
    dp.include_router(business_router)
    backup_task = (
        asyncio.create_task(automatic_backup_loop(bot))
        if settings.backup_enabled else None
    )
    alert_task = asyncio.create_task(alert_monitor_loop(bot))
    website_monitoring_task = asyncio.create_task(website_monitoring_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        for task in (
            backup_task,
            alert_task,
            website_monitoring_task,
            deploy_recovery_task,
        ):
            if task:
                task.cancel()
        for task in (
            backup_task,
            alert_task,
            website_monitoring_task,
            deploy_recovery_task,
        ):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await proxy.stop()
