# Ansible — EC2 setup

## Prerequisites

1. EC2 is running (`terraform apply` done)
2. You can SSH: `ssh -i ~/.ssh/RonKey.pem ubuntu@<EC2_IP>`
3. Ansible installed locally: `brew install ansible` (or `pip install ansible`)

## Inventory

Update `inventory.ini` with your EC2 public IP:

```ini
[app]
YOUR_EC2_IP ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/RonKey.pem
```

Get the IP with:

```bash
cd ../terraform && terraform output -raw instance_public_ip
```

## Run

```bash
cd ansible
ansible-playbook configure-app.yml
```

Or explicitly:

```bash
ansible-playbook -i inventory.ini configure-app.yml
```

## Test connection first

```bash
ansible app -m ping
```
