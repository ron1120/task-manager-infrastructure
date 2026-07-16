#!/usr/bin/env bash
# Export EIP from configure-env/.env into the current shell.
#
# Usage:
#   source configure-env/export-env.sh
#   echo $EIP

_SCRIPT="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "$_SCRIPT")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  echo "Create it: cp ${SCRIPT_DIR}/env.example ${SCRIPT_DIR}/.env" >&2
  return 1 2>/dev/null || exit 1
fi

# Read EIP only (ignore other keys / comments)
EIP="$(grep -E '^[[:space:]]*EIP=' "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"

if [[ -z "${EIP}" ]]; then
  echo "EIP is empty in $ENV_FILE" >&2
  return 1 2>/dev/null || exit 1
fi

export EIP
echo "Exported EIP=${EIP}"
