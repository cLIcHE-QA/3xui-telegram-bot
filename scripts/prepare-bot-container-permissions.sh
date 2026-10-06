#!/usr/bin/env bash
set -Eeuo pipefail

BOT_UID="${BOT_UID:-10001}"
BOT_GID="${BOT_GID:-10001}"
ENV_FILE="${ENV_FILE:-.env}"
DATA_DIR="${DATA_DIR:-./data}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (for example: sudo $0)." >&2
  exit 2
fi

if ! command -v setfacl >/dev/null 2>&1; then
  echo "setfacl is required. Install the host 'acl' package first." >&2
  exit 2
fi

if [[ ! "${BOT_UID}" =~ ^[1-9][0-9]*$ ]] || [[ ! "${BOT_GID}" =~ ^[1-9][0-9]*$ ]]; then
  echo "BOT_UID and BOT_GID must be positive numeric IDs." >&2
  exit 2
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing env file: ${ENV_FILE}" >&2
  exit 2
fi

read_env() {
  local key="$1"
  local fallback="$2"
  local value
  value="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true)"
  if [[ -z "${value}" ]]; then
    printf '%s' "${fallback}"
  else
    printf '%s' "${value}"
  fi
}

XUI_DIR="$(read_env BACKUP_XUI_DIR_HOST_PATH /etc/x-ui)"
NGINX_CONF_DIR="$(read_env BACKUP_NGINX_CONF_HOST_PATH /opt/mtproxyl-nginx/conf)"
NGINX_LOG_DIR="$(read_env NGINX_LOG_HOST_PATH /var/log/nginx)"

grant_parent_traverse() {
  local target="$1"
  local current
  current="$(dirname "$(realpath -m "${target}")")"
  while [[ "${current}" != "/" && -n "${current}" ]]; do
    setfacl -m "u:${BOT_UID}:--x" "${current}"
    current="$(dirname "${current}")"
  done
}

grant_file_read() {
  local target="$1"
  grant_parent_traverse "${target}"
  setfacl -m "u:${BOT_UID}:r--" "${target}"
}

grant_tree_read() {
  local target="$1"
  if [[ ! -d "${target}" ]]; then
    echo "Required backup/log source directory does not exist: ${target}" >&2
    exit 2
  fi
  grant_parent_traverse "${target}"
  # Existing entries: directories need traverse/read, regular files read only.
  find "${target}" -xdev -type d -exec setfacl -m "u:${BOT_UID}:r-x" {} +
  find "${target}" -xdev -type f -exec setfacl -m "u:${BOT_UID}:r--" {} +

  # Future files such as SQLite WAL/SHM and rotated nginx logs must remain
  # readable after the initial rollout. Default ACLs propagate through new
  # subdirectories. The bind mounts are read-only inside the container, so
  # inherited execute permission on a regular source file does not grant write.
  find "${target}" -xdev -type d -exec setfacl -m "d:u:${BOT_UID}:r-x" {} +
}

install -d -o "${BOT_UID}" -g "${BOT_GID}" -m 0700 "${DATA_DIR}"
find "${DATA_DIR}" -xdev -exec chown "${BOT_UID}:${BOT_GID}" {} +
find "${DATA_DIR}" -xdev -type d -exec chmod 0700 {} +
find "${DATA_DIR}" -xdev -type f -exec chmod 0600 {} +

chmod 0600 "${ENV_FILE}"
grant_file_read "${ENV_FILE}"
grant_tree_read "${XUI_DIR}"
grant_tree_read "${NGINX_CONF_DIR}"
grant_tree_read "${NGINX_LOG_DIR}"

echo "Prepared least-privilege bot filesystem access:"
echo "  runtime uid:gid = ${BOT_UID}:${BOT_GID}"
echo "  writable data  = ${DATA_DIR}"
echo "  read-only env  = ${ENV_FILE}"
echo "  read-only x-ui = ${XUI_DIR}"
echo "  read-only nginx config = ${NGINX_CONF_DIR}"
echo "  read-only nginx logs   = ${NGINX_LOG_DIR}"
