# Terraform — EC2 + VPC + persistent EIP

## Keep Elastic IP after destroy

Terraform creates an EIP tagged `Name = <project_name>-eip` with
`lifecycle.prevent_destroy = true`.

| Action | Result |
|--------|--------|
| `terraform destroy` | **Fails** on EIP (by design) |
| `./destroy-keep-eip.sh` | Destroys EC2/VPC/etc., **keeps EIP** |
| Next `terraform apply` | Reuses existing EIP by tag |

```bash
# Safe destroy (keeps Elastic IP)
./destroy-keep-eip.sh

# Or manually:
terraform state rm 'aws_eip.app[0]'
terraform destroy
```

After that, the public IP stays the same on the next apply.
