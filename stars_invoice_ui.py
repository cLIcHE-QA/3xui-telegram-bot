from __future__ import annotations

from aiogram import Bot


async def stars_invoice_title(bot: Bot) -> str:
    """Use the bot's Telegram display name, not the purchased plan name."""
    me = await bot.me()
    # Telegram invoice titles are limited to 32 characters.
    return me.full_name[:32]
