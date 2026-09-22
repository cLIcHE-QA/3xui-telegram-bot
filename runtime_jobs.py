import asyncio

# Shared in-process lock for full backup creation. Both the scheduled job and
# manual admin actions import this lock, preventing overlapping archive builds.
backup_lock = asyncio.Lock()
