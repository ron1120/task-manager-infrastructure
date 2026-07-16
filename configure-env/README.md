# Configure environment

Single source of truth for the EC2 Elastic IP.

## Files

| File | Purpose |
|------|---------|
| `env.example` | Template (committed) |
| `.env` | Your EIP (gitignored) |
| `export-env.sh` | Exports `EIP` into your shell |

## Setup

```bash
cd configure-env
cp env.example .env
# Edit .env — set EIP=your.elastic.ip
```

## Export EIP

```bash
source configure-env/export-env.sh
echo $EIP
```

Ansible reads `EIP` from `.env` automatically via `ansible/inventory.sh` — no need to export for playbooks.

```bash
cd ansible/playbooks
ansible-playbook configure-app.yml
```
