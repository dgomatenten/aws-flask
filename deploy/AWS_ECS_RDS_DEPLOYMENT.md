# AWS ECS + RDS PostgreSQL Deployment Guide

This document is a complete runbook to host this Flask app on AWS ECS (Fargate) with RDS PostgreSQL.

## 1) What you will deploy

- ECS Fargate service for the Flask API container.
- RDS PostgreSQL instance in private subnets.
- Secrets Manager for app and DB secrets.
- ECR repository for container images.
- CloudWatch Logs for container logs.
- Optional GitHub Actions CI/CD pipeline (already included in this repo).

## 2) Prerequisites

- AWS account with permissions for IAM, VPC, RDS, ECS, ECR, Secrets Manager, CloudWatch.
- AWS CLI v2 configured locally.
- Docker installed locally.
- GitHub repository already created for this project.

Install AWS CLI v2 on Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y awscli
aws --version
```

Expected output starts with `aws-cli/2`.

If apt install is unavailable in your environment, use the official AWS installer:

```bash
cd /tmp
curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip -q awscliv2.zip
./aws/install --bin-dir $HOME/.local/bin --install-dir $HOME/.local/aws-cli --update
aws --version
```

Verify tools:

```bash
aws --version
docker --version
git --version
```

Set environment variables once per terminal session:

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export APP_NAME=aws-flask-auth
export ECR_REPO=aws-flask-auth
export DB_NAME=flask_auth
export DB_USER=flask_user
export DB_PASSWORD='ChangeThisToStrongPassword123!'
export SECRET_KEY='ChangeThisToLongRandomSecretKey'
```

## 3) Create networking (VPC, subnets, security groups)

Use your existing production VPC if you already have one.
If not, create one with:

- 2 public subnets for ECS tasks (no load balancer setup).
- 2 private subnets for RDS.

Security groups:

- ECS SG: allow inbound 8000 from trusted client CIDR(s).
- RDS SG: allow inbound 5432 from ECS SG only.

You can create SGs with CLI after you know your VPC ID:

```bash
export VPC_ID=vpc-xxxxxxxx
export TRUSTED_INGRESS_CIDR=0.0.0.0/0

ECS_SG_ID=$(aws ec2 create-security-group \
  --group-name ${APP_NAME}-ecs-sg \
  --description "ECS SG for ${APP_NAME}" \
  --vpc-id "$VPC_ID" \
  --query GroupId --output text)

RDS_SG_ID=$(aws ec2 create-security-group \
  --group-name ${APP_NAME}-rds-sg \
  --description "RDS SG for ${APP_NAME}" \
  --vpc-id "$VPC_ID" \
  --query GroupId --output text)

aws ec2 authorize-security-group-ingress --group-id "$ECS_SG_ID" --protocol tcp --port 8000 --cidr "$TRUSTED_INGRESS_CIDR"
aws ec2 authorize-security-group-ingress --group-id "$RDS_SG_ID" --protocol tcp --port 5432 --source-group "$ECS_SG_ID"
```

Note:

- For production, replace `0.0.0.0/0` with a strict CIDR list (office/VPN/API Gateway sources).

## 4) Create RDS PostgreSQL

Create DB subnet group from your private subnets:

```bash
export PRIVATE_SUBNET_1=subnet-aaaaaaaa
export PRIVATE_SUBNET_2=subnet-bbbbbbbb

aws rds create-db-subnet-group \
  --db-subnet-group-name ${APP_NAME}-db-subnet-group \
  --db-subnet-group-description "DB subnet group for ${APP_NAME}" \
  --subnet-ids "$PRIVATE_SUBNET_1" "$PRIVATE_SUBNET_2"
```

Create PostgreSQL instance:

```bash
aws rds create-db-instance \
  --db-instance-identifier ${APP_NAME}-db \
  --engine postgres \
  --engine-version 16.3 \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 \
  --master-username "$DB_USER" \
  --master-user-password "$DB_PASSWORD" \
  --db-name "$DB_NAME" \
  --vpc-security-group-ids "$RDS_SG_ID" \
  --db-subnet-group-name ${APP_NAME}-db-subnet-group \
  --backup-retention-period 7 \
  --storage-encrypted \
  --no-publicly-accessible
```

Wait until available:

```bash
aws rds wait db-instance-available --db-instance-identifier ${APP_NAME}-db
```

Get RDS endpoint:

```bash
export DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier ${APP_NAME}-db \
  --query 'DBInstances[0].Endpoint.Address' --output text)

echo "$DB_HOST"
```

## 5) Store runtime secrets in Secrets Manager

Create app secret:

```bash
aws secretsmanager create-secret \
  --name flask/prod/app \
  --secret-string "{\"SECRET_KEY\":\"$SECRET_KEY\"}"
```

Create DB secret:

```bash
aws secretsmanager create-secret \
  --name flask/prod/db \
  --secret-string "{\"DB_HOST\":\"$DB_HOST\",\"DB_NAME\":\"$DB_NAME\",\"DB_USER\":\"$DB_USER\",\"DB_PASSWORD\":\"$DB_PASSWORD\"}"
```

Get ARNs:

```bash
export APP_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id flask/prod/app --query ARN --output text)
export DB_SECRET_ARN=$(aws secretsmanager describe-secret --secret-id flask/prod/db --query ARN --output text)

echo "$APP_SECRET_ARN"
echo "$DB_SECRET_ARN"
```

## 6) Create ECR repository and push image

```bash
aws ecr create-repository --repository-name "$ECR_REPO" || true

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

cd /home/dgoma/app_dev/aws-flask
docker build -t ${ECR_REPO}:latest .
docker tag ${ECR_REPO}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest
```

## 7) Create IAM roles for ECS

You need two roles:

- Task execution role: pull image, write logs, read secrets at startup.
- Task role: app runtime IAM permissions if needed.

Minimum policies:

- `AmazonECSTaskExecutionRolePolicy` on execution role.
- `secretsmanager:GetSecretValue` permission on your two secret ARNs.

If you use KMS customer key for secrets, also allow `kms:Decrypt`.

## 8) Prepare ECS task definition

Start from:

- deploy/ecs/task-definition.template.json

Update placeholders:

- `<account-id>` with your account ID.
- `<region>` with your region.
- `executionRoleArn` and `taskRoleArn` with your IAM roles.
- image URI to your ECR image.
- secret ARNs to your actual secret ARNs and keys.

For JSON-key mapping format in ECS secret `valueFrom`, use:

- `<secret-arn>:SECRET_KEY::`
- `<secret-arn>:DB_HOST::`
- `<secret-arn>:DB_NAME::`
- `<secret-arn>:DB_USER::`
- `<secret-arn>:DB_PASSWORD::`

## 9) Create ECS cluster

```bash
aws ecs create-cluster --cluster-name ${APP_NAME}-cluster
```

## 10) Create ECS service without load balancer

Choose public subnets for ECS tasks so the API is reachable directly by task public IP:

```bash
export PUBLIC_SUBNET_1=subnet-cccccccc
export PUBLIC_SUBNET_2=subnet-dddddddd
```

## 11) Register task definition and create ECS service

Register task definition:

```bash
aws ecs register-task-definition --cli-input-json file://deploy/ecs/task-definition.template.json
```

Create service in private subnets:

```bash
aws ecs create-service \
  --cluster ${APP_NAME}-cluster \
  --service-name ${APP_NAME}-service \
  --task-definition ${APP_NAME} \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PUBLIC_SUBNET_1,$PUBLIC_SUBNET_2],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}"
```

Important behavior without a load balancer:

- ECS tasks get dynamic public IPs when redeployed.
- If you scale to more than one task, clients must choose one task IP manually.
- No managed blue/green routing or ALB health checks.

## 12) Initialize DB table and seed users

This app auto-creates tables on startup through SQLAlchemy `create_all()`.

Optional manual SQL method:

```bash
psql "host=$DB_HOST port=5432 dbname=$DB_NAME user=$DB_USER password=$DB_PASSWORD sslmode=require" -f db/sql/001_create_users_table.sql
```

Seed default users by running one-off task command override:

- Use the same task definition and network as service.
- Override command to `python seed_default_users.py`.

Alternative quick approach:

- Temporarily run container in environment with DB connectivity and execute `python seed_default_users.py`.

## 13) Validate deployment

Get running task ENI public IP:

```bash
TASK_ARN=$(aws ecs list-tasks --cluster ${APP_NAME}-cluster --service-name ${APP_NAME}-service --query 'taskArns[0]' --output text)
ENI_ID=$(aws ecs describe-tasks --cluster ${APP_NAME}-cluster --tasks "$TASK_ARN" --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
TASK_PUBLIC_IP=$(aws ec2 describe-network-interfaces --network-interface-ids "$ENI_ID" --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
echo "$TASK_PUBLIC_IP"
```

Health check:

```bash
curl http://$TASK_PUBLIC_IP:8000/health
```

Login API:

```bash
curl -i -X POST http://$TASK_PUBLIC_IP:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

## 14) Set up GitHub Actions deployment

This repository already contains workflow:

- .github/workflows/deploy-ecs.yml

Configure repository secrets in GitHub:

- AWS_ROLE_TO_ASSUME
- AWS_REGION
- ECR_REPOSITORY
- ECS_CLUSTER
- ECS_SERVICE

See:

- deploy/ecs/github-secrets.required.txt

Important:

- Do not place DB credentials in GitHub secrets.
- Keep runtime DB/app secrets in AWS Secrets Manager only.

## 15) Observability and operations

- Check ECS service events for deployment issues.
- Check task logs in CloudWatch log group `/ecs/aws-flask-auth`.
- Set CloudWatch alarms for:
  - ECS service running task count.
  - ECS task health check failures.
  - RDS CPU and free storage.

## 16) Rollback

If a deployment fails:

- In ECS, update service to previous task definition revision.
- Confirm container health checks become healthy again.

## 17) Security best practices

- Keep RDS in private subnets.
- If no ALB is used, lock `ECS_SG_ID` ingress CIDR tightly.
- For HTTPS without ALB, terminate TLS in container or place CloudFront/API Gateway in front.
- Restrict security group ingress to least privilege.
- Rotate Secrets Manager values regularly.
- Enable RDS automated backups and deletion protection.

## 18) Cost cleanup

Delete resources when not needed:

- ECS service and cluster.
- RDS instance and subnet group.
- ECR repository images.
- Secrets (after recovery window decision).
- CloudWatch log group.

## 19) Existing project files used in this runbook

- app/config.py
- app/routes.py
- db/sql/001_create_users_table.sql
- seed_default_users.py
- deploy/ecs/task-definition.template.json
- .github/workflows/deploy-ecs.yml
