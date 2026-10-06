from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ContainerLeastPrivilegeContractTests(unittest.TestCase):
    def test_image_uses_dedicated_non_root_identity(self):
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER 10001:10001", text)
        self.assertIn("COPY . .", text)
        self.assertNotIn("COPY --chown=10001:10001", text)
        self.assertIn("chown -R 0:0 /app", text)
        self.assertIn("chmod -R u=rwX,go=rX /app", text)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", text)
        self.assertIn("HOME=/tmp", text)
        self.assertNotIn("USER root", text)

    def test_compose_drops_privilege_and_keeps_only_data_writable(self):
        text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("read_only: true", text)
        self.assertIn("no-new-privileges:true", text)
        self.assertIn("cap_drop:", text)
        self.assertIn("- ALL", text)
        self.assertIn("/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777", text)
        self.assertIn("./data:/app/data", text)
        self.assertIn("/app/backup_sources/bot.env:ro", text)
        self.assertIn("/app/backup_sources/x-ui:ro", text)
        self.assertIn("/app/backup_sources/nginx:ro", text)
        self.assertIn("/app/log_sources/nginx:ro", text)
        self.assertNotIn("privileged: true", text)
        self.assertNotIn("/var/run/docker.sock", text)

    def test_host_permission_preflight_is_bounded(self):
        text = (
            ROOT / "scripts" / "prepare-bot-container-permissions.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('BOT_UID="${BOT_UID:-10001}"', text)
        self.assertIn('BOT_GID="${BOT_GID:-10001}"', text)
        self.assertIn("setfacl", text)
        self.assertIn('install -d -o "${BOT_UID}" -g "${BOT_GID}" -m 0700 "${DATA_DIR}"', text)
        self.assertIn('find "${DATA_DIR}" -xdev -exec chown', text)
        self.assertIn('find "${target}" -xdev -type f -exec setfacl', text)
        self.assertIn('setfacl -m "d:u:${BOT_UID}:r-x"', text)
        deploy = (ROOT / "scripts" / "deploy-release.sh").read_text(encoding="utf-8")
        self.assertIn("prepare_container_permissions()", deploy)
        self.assertIn("prepare_container_permissions", deploy)
        self.assertIn("target release requires least-privilege host permissions", deploy)
        self.assertNotIn("chmod -R 777", text)
        self.assertNotIn("chown -R root", text)


if __name__ == "__main__":
    unittest.main()
