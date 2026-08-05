# Flask + PostgreSQL Sample for AWS ECS + RDS

This sample provides:
- Login API
- Logout API
- Healthcheck API with DB connectivity check

## 1) Project structure

- app/ - Flask application package
- run.py - WSGI entrypoint
- bootstrap_admin.py - create first user
- Dockerfile - container image for ECS
- deploy/ecs/task-definition.template.json - ECS task definition example with Secrets Manager

## 2) Local run (dev only)

1. Create local env file from example:

   cp .env.example .env

2. Start PostgreSQL and API:

   docker compose up --build -d

3. Create bootstrap user:

   docker compose exec api python bootstrap_admin.py

4. Test healthcheck:

   curl http://localhost:8000/health

## 2.1) Create users table manually in PostgreSQL

If you want to create the table using SQL directly:

psql "host=localhost port=5432 dbname=flask_auth user=flask_user password=flask_password" -f db/sql/001_create_users_table.sql

Note:
- PostgreSQL has a reserved keyword `user`, so this project uses table name `users`.

## 3) APIs

### Healthcheck

- GET /health
- Returns 200 when DB is reachable, 503 otherwise

### Login

- POST /auth/login
- Body:

  {
    "username": "admin",
    "password": "admin123"
  }

### Logout

- POST /auth/logout

### Current Session

- GET /auth/me

## 3.1) Seed default users

Run the seed script:

python seed_default_users.py

Or inside Docker:

docker compose exec api python seed_default_users.py

Default users inserted (if not already present):
- admin / admin123
- developer / dev123

You can override using environment variables:
- DEFAULT_ADMIN_PASSWORD
- DEFAULT_DEVELOPER_PASSWORD

Or provide custom JSON list:

DEFAULT_USERS_JSON='[{"username":"ops","password":"ops123"},{"username":"qa","password":"qa123"}]' python seed_default_users.py

## 4) AWS Secrets Manager (production)

Do not use `.env` in ECS production. Store secrets in AWS Secrets Manager and map them in ECS task definition.

Required secret keys used by app:
- SECRET_KEY
- DB_HOST
- DB_NAME
- DB_USER
- DB_PASSWORD

You can keep `DB_PORT=5432` and `DB_SSLMODE=require` as normal environment variables or secrets.

## 5) Example: create secrets with AWS CLI

Create app secret:

aws secretsmanager create-secret \
  --name flask/prod/app \
  --secret-string '{"SECRET_KEY":"replace-with-strong-random-key"}'

Create db secret:

aws secretsmanager create-secret \
  --name flask/prod/db \
  --secret-string '{"DB_HOST":"your-rds-endpoint","DB_NAME":"flask_auth","DB_USER":"flask_user","DB_PASSWORD":"replace-with-strong-password"}'

Then reference them in ECS task definition `secrets` section (see deploy/ecs/task-definition.template.json).

## 6) Build and push image to ECR

aws ecr create-repository --repository-name aws-flask-auth

aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com

docker build -t aws-flask-auth .
docker tag aws-flask-auth:latest <account-id>.dkr.ecr.<region>.amazonaws.com/aws-flask-auth:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/aws-flask-auth:latest

## 7) ECS + RDS notes

- Place ECS service in private subnets with NAT (or proper outbound path).
- Allow ECS task security group to access RDS on port 5432.
- Use IAM task execution role permission for Secrets Manager reads.
- Use an ALB for public HTTP access.

## 8) Deploy through GitHub Actions

Yes, deployment can be fully done through GitHub.

Pipeline file:
- .github/workflows/deploy-ecs.yml

What it does on push to main:
1. Builds Docker image
2. Pushes image to ECR
3. Renders ECS task definition with the new image tag
4. Deploys updated task definition to ECS service

Required GitHub repository secrets:
- AWS_ROLE_TO_ASSUME
- AWS_REGION
- ECR_REPOSITORY
- ECS_CLUSTER
- ECS_SERVICE

See full list in:
- deploy/ecs/github-secrets.required.txt

Important security note:
- Keep runtime secrets (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, SECRET_KEY) in AWS Secrets Manager.
- Do not store runtime database credentials in GitHub secrets.
