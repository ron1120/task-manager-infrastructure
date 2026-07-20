terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

#####################################
# Existing VPC support
#####################################

data "aws_vpc" "existing" {
  count = var.existing_vpc_id != "" ? 1 : 0
  id    = var.existing_vpc_id
}

data "aws_internet_gateway" "existing" {
  count = var.existing_vpc_id != "" ? 1 : 0

  filter {
    name   = "attachment.vpc-id"
    values = [var.existing_vpc_id]
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  vpc_id = var.existing_vpc_id != "" ? data.aws_vpc.existing[0].id : aws_vpc.main[0].id

  internet_gateway_id = var.existing_vpc_id != "" ? data.aws_internet_gateway.existing[0].id : aws_internet_gateway.main[0].id
}

#####################################
# VPC
#####################################

resource "aws_vpc" "main" {
  count = var.existing_vpc_id == "" ? 1 : 0

  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  count = var.existing_vpc_id == "" ? 1 : 0

  vpc_id = local.vpc_id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

#####################################
# Public Subnet
#####################################

resource "aws_subnet" "public" {
  vpc_id                  = local.vpc_id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

#####################################
# Routing
#####################################

resource "aws_route_table" "public" {
  vpc_id = local.vpc_id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = local.internet_gateway_id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

#####################################
# Security Group
#####################################

resource "aws_security_group" "app" {
  name        = "${var.project_name}-sg"
  description = "Security group for task manager application"
  vpc_id      = local.vpc_id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_cidr_blocks
  }

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Frontend container (development only)
  ingress {
    description = "Frontend"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Backend container (development only)
  ingress {
    description = "Backend API"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Database intentionally NOT exposed publicly
  # PostgreSQL should only be accessible through Docker networking.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sg"
  }
}

# Separate rules (AWS provider 5.x often ignores new inline ingress on existing SGs)
resource "aws_vpc_security_group_ingress_rule" "grafana" {
  security_group_id = aws_security_group.app.id
  description       = "Grafana"
  from_port         = 3001
  to_port           = 3001
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "prometheus" {
  security_group_id = aws_security_group.app.id
  description       = "Prometheus"
  from_port         = 9090
  to_port           = 9090
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

#####################################
# Ubuntu AMI
#####################################

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = [
      "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"
    ]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

#####################################
# EC2 Instance
#####################################

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name               = var.key_name

  associate_public_ip_address = true

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_size           = var.root_volume_gb
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name = "${var.project_name}-ec2"
  }
}

#####################################
# Elastic IP
#
# EIP is created once and kept forever.
# - prevent_destroy blocks accidental deletion via terraform destroy
# - If an EIP with tag Name = "${project_name}-eip" already exists,
#   Terraform reuses it instead of creating a new one
#
# To destroy everything EXCEPT the EIP:
#   ./destroy-keep-eip.sh
#   # or manually:
#   terraform state rm 'aws_eip.app[0]'
#   terraform destroy
#####################################

data "aws_eips" "existing" {
  filter {
    name   = "tag:Name"
    values = ["${var.project_name}-eip"]
  }
}

locals {
  eip_exists        = length(data.aws_eips.existing.allocation_ids) > 0
  eip_allocation_id = local.eip_exists ? data.aws_eips.existing.allocation_ids[0] : aws_eip.app[0].id
  eip_public_ip     = local.eip_exists ? data.aws_eips.existing.public_ips[0] : aws_eip.app[0].public_ip
}

resource "aws_eip" "app" {
  count  = local.eip_exists ? 0 : 1
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }

  # Keep this IP after terraform destroy (must state-rm before destroy)
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = local.eip_allocation_id
}

#####################################
# Variables
#####################################

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Public subnet CIDR"
  type        = string
  default     = "10.0.1.0/24"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
}

variable "root_volume_gb" {
  description = "Root volume size"
  type        = number
  default     = 30
}

variable "existing_vpc_id" {
  description = "Reuse an existing VPC instead of creating one"
  type        = string
  default     = ""
}

variable "ssh_cidr_blocks" {
  description = "CIDRs allowed to SSH to the instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

#####################################
# Outputs
#####################################

output "instance_id" {
  value = aws_instance.app.id
}

output "instance_public_ip" {
  value = local.eip_public_ip
}

output "eip_allocation_id" {
  value = local.eip_allocation_id
}

output "vpc_id" {
  value = local.vpc_id
}

output "public_subnet_id" {
  value = aws_subnet.public.id
}