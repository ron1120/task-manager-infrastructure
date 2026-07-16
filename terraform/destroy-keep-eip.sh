#!/usr/bin/env bash
# Destroy all Terraform resources but KEEP the Elastic IP in AWS.
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Removing EIP from Terraform state (AWS resource is kept)..."
if terraform state list 2>/dev/null | grep -q '^aws_eip.app\[0\]$'; then
  terraform state rm 'aws_eip.app[0]'
else
  echo "    (EIP not in state — already external / reused)"
fi

echo "==> Destroying remaining resources..."
terraform destroy "$@"

echo "==> Done. EIP tagged '${project_name:-task-manager}-eip' should still exist in AWS."
echo "    Next terraform apply will reuse it via the Name tag."
