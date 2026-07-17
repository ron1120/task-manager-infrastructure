#!/usr/bin/env bash
# Dynamic Ansible inventory — reads EIP from configure-env/.env on your PC
# Must be executable: chmod +x inventory.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../configure-env/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "{\"_meta\":{\"hostvars\":{}},\"app\":{\"hosts\":[],\"vars\":{}}}"
  exit 0
fi

EIP="$(grep -E '^[[:space:]]*EIP=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'" | tr -d '[:space:]')"

if [[ -z "${EIP}" ]]; then
  echo "EIP is empty in $ENV_FILE" >&2
  exit 1
fi

if [[ "$1" == "--list" ]]; then
  cat <<EOF
{
  "app": {
    "hosts": ["${EIP}"],
    "vars": {
      "ansible_user": "ubuntu",
      "ansible_python_interpreter": "/usr/bin/python3",
      "ansible_ssh_private_key_file": "${HOME}/.ssh/RonKey.pem",
      "public_host": "${EIP}"
    }
  },
  "_meta": {
    "hostvars": {}
  }
}
EOF
elif [[ "$1" == "--host" ]]; then
  echo '{}'
else
  echo "Usage: $0 --list|--host <hostname>" >&2
  exit 1
fi
