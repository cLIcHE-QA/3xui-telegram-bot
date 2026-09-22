"""One-time integration on the feature branch; removed before the final PR.

Only exact reviewed v4.8.0 files are accepted. No runtime data or live APIs are
accessed. This script is never used by the application.
"""
from pathlib import Path
import hashlib

EXPECTED = {
    'xui.py': 'd5c792a680c04505aa6356fce396bb00aa215668',
    'bot.py': 'acc118805f40825e2bc79bbf39913c558fb54e25',
    'admin_auth.py': 'e62bec636a600892230ffd3be448cf677646b6ee',
    'admin_observability.py': 'c0e70ebfa4bfdff0bed619a1e9421d7c99942e7b',
    'advanced_nodes.py': '60d92432050928ab459c1314d8a48b169722a124',
    'backup_manager.py': '0572c44ca824ce45a27631ba9f2ed763bbbd5d4a',
    'system_backup.py': 'd154f04798a1ab30048660cb6ed759461b884aa2',
    'README.md': '921f9b8dd2cc3b7e488decc684e6d5671ece0779',
    'CHANGELOG.md': '6ad5109e7384496a499f362a6b48db003a516c45',
    '.dockerignore': '4f6d1cf1b3863c826c1bb7b7b682e09e14e06a99',
}


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f'Expected one source anchor, found {text.count(old)}: {old[:100]!r}')
    return text.replace(old, new, 1)


def main():
    sources = {}
    for name, expected in EXPECTED.items():
        body = Path(name).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest()
        if actual != expected:
            raise RuntimeError(f'{name}: source changed since review; refusing to patch')
        sources[name] = body.decode('utf-8')

    sources['xui.py'] = replace_once(sources['xui.py'], 'import aiohttp\n', 'import aiohttp\nfrom version_api import VersionAPIMixin\n')
    sources['xui.py'] = replace_once(sources['xui.py'], 'class XUIClient:', 'class XUIClient(VersionAPIMixin):')
    for name in ['backup_manager.py', 'system_backup.py']:
        sources[name] = replace_once(sources[name], 'from pathlib import Path\n', 'from pathlib import Path\nfrom version import APP_VERSION\n')
    sources['backup_manager.py'] = replace_once(sources['backup_manager.py'], 'version: str = "4.7.0"', 'version: str = APP_VERSION')
    sources['system_backup.py'] = replace_once(sources['system_backup.py'], 'version="4.7.0"', 'version=APP_VERSION')

    bot = sources['bot.py']
    bot = replace_once(bot, 'from xui import XUIClient, XUIError, NodeInfo\n',
        'from xui import XUIClient, XUIError, NodeInfo\nfrom version import APP_VERSION\nfrom version_api import VersionAPIError\nfrom versions_updates import versions_router\n')
    bot = replace_once(bot, 'await message.answer("3x-ui Telegram bot v4.8.0", reply_markup=user_menu())',
        'await message.answer(f"3x-ui Telegram bot v{APP_VERSION}", reply_markup=user_menu())')
    bot = replace_once(bot, 'f"Created by Telegram bot v4.8.0', 'f"Created by Telegram bot v{APP_VERSION}')
    anchor = 'def system_menu() -> InlineKeyboardMarkup:\n    return InlineKeyboardMarkup(inline_keyboard=[\n'
    bot = replace_once(bot, anchor, anchor + '        [InlineKeyboardButton(text="\U0001f9e9 Versions & Updates", callback_data="admin:versions")],\n')
    anchor = 'def master_detail_keyboard() -> InlineKeyboardMarkup:\n    return InlineKeyboardMarkup(inline_keyboard=[\n'
    bot = replace_once(bot, anchor, anchor + '''        [
            InlineKeyboardButton(text="3x-ui updates", callback_data="admin:ver:panel:m"),
            InlineKeyboardButton(text="Xray Core", callback_data="admin:ver:xray:m:0"),
        ],
''')
    old = '        [InlineKeyboardButton(text="\u2b06\ufe0f Update 3x-ui", callback_data=f"admin:nodectl:{node_id}:updatepanel")],\n'
    new = '        [InlineKeyboardButton(text="\u2b06\ufe0f Update 3x-ui", callback_data=f"admin:ver:panel:n{node_id}")],\n'
    new += '        [InlineKeyboardButton(text="Xray Core", callback_data=f"admin:ver:xray:n{node_id}:0")],\n'
    bot = replace_once(bot, old, new)
    bot = replace_once(bot, 'callback_data="admin:coming:panels"', 'callback_data="admin:versions"')
    anchor = '    if status:\n        xray = status.get("xray") or {}\n'
    new = '''    if status:
        try:
            panel_info = await xui.get_panel_update_info()
            panel_version = str(panel_info.get("currentVersion") or "unavailable")
        except VersionAPIError:
            panel_version = "unavailable"
        lines.append(f"3x-ui: {panel_version}")
        xray = status.get("xray") or {}
'''
    bot = replace_once(bot, anchor, new)
    bot = replace_once(bot, '    dp.include_router(router)\n', '    dp.include_router(router)\n    dp.include_router(versions_router)\n')
    sources['bot.py'] = bot

    nodes = sources['advanced_nodes.py']
    nodes = replace_once(nodes, 'from xui import XUIClient, XUIError\n', 'from xui import XUIClient, XUIError\nfrom versions_updates import show_panel_screen\n')
    start = r'@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:updatepanel$"))'
    end = r'@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:deleteask$"))'
    left, right = nodes.index(start), nodes.index(end)
    replacement = r'''@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:updatepanel$"))
@advanced_nodes_router.callback_query(F.data.regexp(r"^admin:nodectl:\d+:updatepanel:run$"))
async def node_update_panel_legacy(call: CallbackQuery):
    # Old keyboards cannot bypass the new backup, locking and confirmation gates.
    ok, _ = await authorize_callback(db, settings, call, minimum="admin")
    if not ok:
        return
    node_id = _node_id_from_callback(call.data or "")
    await show_panel_screen(call, f"n{node_id}")


'''
    sources['advanced_nodes.py'] = nodes[:left] + replacement + nodes[right:]

    auth = sources['admin_auth.py']
    auth = replace_once(auth, 'from __future__ import annotations\n', 'from __future__ import annotations\n\nimport re\n')
    anchor = 'def required_role_for_callback(data: str) -> str:\n    data = data or ""\n'
    new = anchor + r'''
    if data == "admin:versions":
        return "read_only"
    if data.startswith("admin:ver:unlock:"):
        return "owner"
    if data.startswith("admin:ver:"):
        key = r"(?:m|n[1-9][0-9]{0,18})"
        readonly = rf"admin:ver:(?:(?:target|panel):{key}|xray:{key}:[0-9]+|check:[0-9a-f]{{16}})"
        return "read_only" if re.fullmatch(readonly, data) else "admin"
'''
    sources['admin_auth.py'] = replace_once(auth, anchor, new)
    labels = ''
    for action, label in [('panel.update', '3x-ui update'), ('xray.install', 'Xray install')]:
        for stage in ['prepared', 'started', 'success', 'failed', 'unconfirmed', 'cancelled', 'acknowledged']:
            labels += f'    "{action}.{stage}": "{label}: {stage}",\n'
    sources['admin_observability.py'] = replace_once(sources['admin_observability.py'], 'ACTION_LABELS = {\n', 'ACTION_LABELS = {\n' + labels)

    readme = replace_once(sources['README.md'], '# 3x-ui Telegram bot v4.8.0', '# 3x-ui Telegram bot v4.9.0')
    introduction = '''
## v4.9.0 - Versions & Updates

Open `/admin -> System -> Versions & Updates`. Master/Node cards and
Infrastructure -> Panels link to the same version-management UI.

The module displays 3x-ui/Xray versions, updates 3x-ui through its official
stable-channel updater and lets an administrator select an exact Xray version
(upgrade or downgrade). Each operation creates and checks a fresh backup, then
requires a single-use confirmation valid for five minutes. It verifies the
installed version and running Xray, not merely an HTTP success response.

Node updates require the existing direct admin connection in
`NODE_BACKUP_TARGETS`. Incomplete/invalid backups block installation. There are
no automatic updates or automatic rollback. Uncertain outcomes are recorded and
block new updates until read-only verification or an explicit Owner acknowledgement.
No changes to user provisioning, subscriptions, payments or the SQLite schema.

See [Versions & Updates](docs/VERSIONS_UPDATES.md) for recovery, limitations and
deployment checks. Historical notes below describe their respective releases.

'''
    readme = replace_once(readme, 'Production-oriented Telegram admin panel for 3x-ui.\n', 'Production-oriented Telegram admin panel for 3x-ui.\n' + introduction)
    sources['README.md'] = readme
    changelog = '''## v4.9.0 - Versions & Updates
- Added version dashboard and Master/Node shortcuts.
- Added explicit stable-channel panel updates and exact Xray version selection.
- Fresh validated backup, expiring single-use confirmation, durable target lockout and post-update verification.
- Panel updater run IDs are checked; lost responses never trigger automatic retries.
- Read-only views, Admin+ installation and explicit Owner acknowledgement for uncertain outcomes.
- Reused existing audit/job tables; no SQLite schema changes.
- Centralized APP_VERSION and corrected stale backup manifest versions.
- Added automated API/workflow/integration tests and read-only pull-request CI.

'''
    sources['CHANGELOG.md'] = replace_once(sources['CHANGELOG.md'], '## v4.8.0', changelog + '## v4.8.0')
    sources['.dockerignore'] += '\n.env.*\n!.env.example\ntests/\n.github/\nscripts/\n'

    for name, text in sources.items():
        Path(name).write_text(text, encoding='utf-8')
    print(f'Integrated v4.9.0 into {len(sources)} verified source files.')


if __name__ == '__main__':
    main()
