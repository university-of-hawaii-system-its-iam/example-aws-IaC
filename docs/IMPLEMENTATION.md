# Implementation Guide

This document provides a detailed, step-by-step guide for setting up AWS resources for the UH Groupings IaC project. The infrastructure uses AWS Fargate for serverless container orchestration with RDS PostgreSQL for data, ElastiCache for caching, and AWS Secrets Manager/Parameter Store for configuration management.

## Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Docker installed locally
- Node.js and npm installed
- CDK CLI installed: `npm install -g aws-cdk`
- GitHub repository access for deployment workflows

---

## Phase 1: AWS Account Setup

### 1.1 Create AWS Account and Enable Billing

**Tasks:**
1. Create AWS account or use existing account
2. Enable billing alerts:
   - Go to AWS Billing → Billing Preferences
   - Enable "Receive Billing Alerts"
   - Set up SNS topic for alerts
3. Create root account credentials (if new account)
4. Enable CloudTrail for audit logging

**Verification:**
```bash
aws sts get-caller-identity
```

### 1.2 Create IAM User for Development

**Tasks:**
1. Create IAM user "uh-groupings-dev":
   - Go to IAM → Users → Create User
   - Enable console access with strong password
   - Generate access keys for CLI access
2. Create IAM policy "uh-groupings-dev-policy" with permissions:
   - EC2 (VPC, subnets, security groups, instances)
   - ECS (clusters, services, task definitions)
   - RDS (databases, security groups)
   - ElastiCache (clusters)
   - ECR (repositories)
   - S3 (bucket creation and access)
   - Secrets Manager (secret creation/management)
   - Systems Manager (Parameter Store)
   - CloudWatch (logs, alarms)
   - CloudFormation (stack management)
   - IAM (role creation for services)
3. Attach policy to user
4. Save access keys securely

**Verification:**
```bash
aws configure
aws iam list-users
```

### 1.3 Create IAM Roles for ECS Tasks

**Tasks:**
1. Create ECS Task Execution Role "uh-groupings-ecs-task-execution-role":
   - Trust relationship: ECS tasks
   - Attach policy: "AmazonECSTaskExecutionRolePolicy"
   - Add permissions for ECR image pull
   - Add permissions for CloudWatch Logs
   - Add permissions for Secrets Manager access
2. Create ECS Task Role "uh-groupings-ecs-task-role":
   - Trust relationship: ECS tasks
   - Add permissions for application-specific resources:
     - RDS database access
     - S3 bucket access
     - ElastiCache access
     - Secrets Manager read access
     - Parameter Store read access

**Verification:**
```bash
aws iam get-role --role-name uh-groupings-ecs-task-execution-role
aws iam get-role --role-name uh-groupings-ecs-task-role
```

---

## Phase 2: Networking Infrastructure

### 2.1 Create VPC

**Tasks:**
1. Create VPC "uh-groupings-vpc":
   - CIDR block: `10.0.0.0/16` (adjustable)
   - Enable DNS hostnames
   - Enable DNS resolution
2. Create Internet Gateway "uh-groupings-igw"
3. Attach Internet Gateway to VPC
4. Enable Flow Logs:
   - Create CloudWatch log group: `/aws/vpc/uh-groupings-flow-logs`
   - Enable Flow Logs to CloudWatch

**Verification:**
```bash
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=uh-groupings-vpc"
aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=uh-groupings-igw"
```

### 2.2 Create Subnets

**Tasks:**
1. Create Public Subnet 1 (AZ-a):
   - Name: "uh-groupings-public-subnet-1a"
   - CIDR: `10.0.1.0/24`
   - Availability Zone: us-east-1a
2. Create Public Subnet 2 (AZ-b):
   - Name: "uh-groupings-public-subnet-1b"
   - CIDR: `10.0.2.0/24`
   - Availability Zone: us-east-1b
3. Create Private Subnet 1 (AZ-a):
   - Name: "uh-groupings-private-subnet-1a"
   - CIDR: `10.0.10.0/24`
   - Availability Zone: us-east-1a
4. Create Private Subnet 2 (AZ-b):
   - Name: "uh-groupings-private-subnet-1b"
   - CIDR: `10.0.11.0/24`
   - Availability Zone: us-east-1b
5. Enable auto-assign public IPv4 for public subnets only

**Verification:**
```bash
aws ec2 describe-subnets --filters "Name=vpc-id,Values=<vpc-id>"
```

### 2.3 Create NAT Gateways

**Tasks:**
1. Create Elastic IP 1 for NAT Gateway 1
2. Create NAT Gateway 1 in Public Subnet 1a
3. Create Elastic IP 2 for NAT Gateway 2
4. Create NAT Gateway 2 in Public Subnet 1b
5. Wait for NAT Gateways to reach "available" state (5-10 minutes)

**Verification:**
```bash
aws ec2 describe-nat-gateways --filters "Name=vpc-id,Values=<vpc-id>"
```

### 2.4 Create Route Tables

**Tasks:**
1. Create Public Route Table "uh-groupings-public-rt":
   - Add route: 0.0.0.0/0 → Internet Gateway
   - Associate with Public Subnet 1a
   - Associate with Public Subnet 1b
2. Create Private Route Table 1a "uh-groupings-private-rt-1a":
   - Add route: 0.0.0.0/0 → NAT Gateway 1
   - Associate with Private Subnet 1a
3. Create Private Route Table 1b "uh-groupings-private-rt-1b":
   - Add route: 0.0.0.0/0 → NAT Gateway 2
   - Associate with Private Subnet 1b

**Verification:**
```bash
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=<vpc-id>"
```

### 2.5 Create Security Groups

**Tasks:**
1. Create ALB Security Group "uh-groupings-alb-sg":
   - Inbound: HTTP (80) from 0.0.0.0/0
   - Inbound: HTTPS (443) from 0.0.0.0/0
   - Outbound: All traffic

2. Create ECS Tasks Security Group "uh-groupings-ecs-sg":
   - Inbound: 3000 (UI) from ALB security group
   - Inbound: 8080 (API) from ALB security group
   - Outbound: All traffic

3. Create RDS Security Group "uh-groupings-rds-sg":
   - Inbound: 5432 (PostgreSQL) from ECS security group
   - Outbound: All traffic

4. Create ElastiCache Security Group "uh-groupings-elasticache-sg":
   - Inbound: 6379 (Redis) from ECS security group
   - Outbound: All traffic

5. Create EFS Security Group "uh-groupings-efs-sg":
   - Inbound: NFS (2049) from ECS security group
   - Outbound: All traffic

**Verification:**
```bash
aws ec2 describe-security-groups --filters "Name=vpc-id,Values=<vpc-id>"
```

---

## Phase 3: Data Layer

### 3.1 Create RDS PostgreSQL Database

**Tasks:**
1. Create DB Subnet Group "uh-groupings-db-subnet-group":
   - Include Private Subnet 1a
   - Include Private Subnet 1b

2. Create RDS Instance:
   - Engine: PostgreSQL 15.x or latest
   - Instance class: db.t3.micro (for dev/test) or db.t3.small (for production)
   - Allocated storage: 100 GB (adjustable)
   - Storage type: gp3
   - DB name: `uh_groupings_db`
   - Master username: `dbadmin`
   - Master password: Generate strong password (store in Secrets Manager - see section 3.3)
   - DB Subnet Group: uh-groupings-db-subnet-group
   - VPC Security Group: uh-groupings-rds-sg
   - Multi-AZ deployment: Yes (for production)
   - Backup retention: 7 days
   - Backup window: 03:00-04:00 UTC
   - Maintenance window: sun:04:00-sun:05:00 UTC
   - Enable CloudWatch monitoring
   - Enable performance insights
   - Enable automated minor version upgrades

3. Wait for DB instance to reach "available" state (10-15 minutes)

4. Create database and schema:
   ```sql
   CREATE DATABASE uh_groupings;
   -- Connect to new database and create schema as needed
   ```

**Verification:**
```bash
aws rds describe-db-instances --db-instance-identifier uh-groupings-db
```

### 3.2 Create ElastiCache Redis Cluster

**Tasks:**
1. Create ElastiCache Subnet Group "uh-groupings-elasticache-subnet-group":
   - Include Private Subnet 1a
   - Include Private Subnet 1b

2. Create Redis Cluster:
   - Cluster name: `uh-groupings-cache`
   - Engine version: 7.0 or latest
   - Node type: cache.t3.micro (for dev/test) or cache.t3.small (for production)
   - Number of cache nodes: 2 (for Multi-AZ)
   - Automatic failover: Enabled
   - Subnet group: uh-groupings-elasticache-subnet-group
   - Security groups: uh-groupings-elasticache-sg
   - Preferred Availability Zones: us-east-1a, us-east-1b
   - Automated backup: Enabled (daily)
   - Snapshot window: 03:00-05:00 UTC
   - Maintenance window: sun:04:00-sun:05:00 UTC
   - CloudWatch metrics: Enabled
   - Enable automatic failover

3. Wait for cluster to reach "available" state (5-10 minutes)

**Verification:**
```bash
aws elasticache describe-cache-clusters --cache-cluster-id uh-groupings-cache
```

### 3.3 Set Up Secrets Manager

**Tasks:**
1. Create RDS Master Password Secret:
   - Name: `uh-groupings/rds/master-password`
   - Secret type: Other type of secret
   - Key-value pairs:
     - `username`: dbadmin
     - `password`: (strong generated password)
   - Rotation: Enable automatic rotation (30 days)

2. Create Application Database Secret:
   - Name: `uh-groupings/database/connection`
   - Key-value pairs:
     - `host`: (RDS endpoint, e.g., uh-groupings-db.xyz.us-east-1.rds.amazonaws.com)
     - `port`: 5432
     - `database`: uh_groupings_db
     - `username`: dbadmin
     - `password`: (from RDS Master Password Secret)

3. Create Redis Secret:
   - Name: `uh-groupings/redis/connection`
   - Key-value pairs:
     - `host`: (ElastiCache primary endpoint)
     - `port`: 6379
     - `auth_token`: (if enabled in Redis)

4. Create API Secrets (application-specific):
   - Name: `uh-groupings/api/secrets`
   - Key-value pairs:
     - `api_key`: (application API key)
     - `jwt_secret`: (JWT signing secret)
     - `external_service_token`: (any external service tokens)

5. Create UI Secrets (if needed):
   - Name: `uh-groupings/ui/secrets`
   - Key-value pairs:
     - `oauth_client_id`: (if using OAuth)
     - `oauth_client_secret`: (if using OAuth)

**Verification:**
```bash
aws secretsmanager list-secrets --filters Key=name,Values=uh-groupings
aws secretsmanager get-secret-value --secret-id uh-groupings/rds/master-password
```

### 3.4 Create Amazon EFS for Log Persistence

**Tasks:**
1. Create EFS File System:
   - Name: `uh-groupings-logs-efs`
   - Performance mode: General Purpose (default)
   - Throughput mode: Bursting (default)
   - Encryption: Enabled (at rest)
   - Enable CloudWatch monitoring

2. Create Mount Targets:
   - Mount target 1 (us-east-1a):
     - Subnet: Private Subnet 1a
     - Security group: Create EFS security group
   - Mount target 2 (us-east-1b):
     - Subnet: Private Subnet 1b
     - Security group: EFS security group

3. Create EFS Security Group "uh-groupings-efs-sg":
   - Inbound: NFS (2049) from ECS security group
   - Outbound: All traffic

4. Create Access Point for logs:
   - Name: `uh-groupings-logs-access-point`
   - File system: uh-groupings-logs-efs
   - Enforce user identity: POSIX user (uid: 1000, gid: 1000)
   - Root directory path: `/`
   - Root directory permissions: 755

5. Wait for mount targets to reach "available" state (2-5 minutes)

6. (Optional) Enable EFS Backup:
   - Create backup plan for daily snapshots
   - Retention: 7 days
   - Purpose: Point-in-time recovery

**Verification:**
```bash
aws efs describe-file-systems --query "FileSystems[?Name=='uh-groupings-logs-efs']"
aws efs describe-mount-targets --file-system-id <efs-id>
aws efs describe-access-points --file-system-id <efs-id>
```

---

## Phase 4: Application Configuration

### 4.1 Set Up Parameter Store

**Tasks:**
1. Create API Configuration Parameters:
   - Name: `/uh-groupings/api/environment`
   - Type: String
   - Value: `production` (or `test`)

   - Name: `/uh-groupings/api/log_level`
   - Type: String
   - Value: `INFO`

   - Name: `/uh-groupings/api/port`
   - Type: String
   - Value: `8080`

   - Name: `/uh-groupings/api/groupings_service_url`
   - Type: String
   - Value: `https://www.groupings.hawaii.edu/api` (or local test endpoint)

   - Name: `/uh-groupings/api/session_timeout`
   - Type: String
   - Value: `3600` (seconds)

2. Create UI Configuration Parameters:
   - Name: `/uh-groupings/ui/environment`
   - Type: String
   - Value: `production` (or `test`)

   - Name: `/uh-groupings/ui/port`
   - Type: String
   - Value: `3000`

   - Name: `/uh-groupings/ui/api_base_url`
   - Type: String
   - Value: `http://localhost:8080/api` (or actual API URL)

   - Name: `/uh-groupings/ui/log_level`
   - Type: String
   - Value: `INFO`

3. Create Common Parameters:
   - Name: `/uh-groupings/common/region`
   - Type: String
   - Value: `us-east-1`

   - Name: `/uh-groupings/common/environment`
   - Type: String
   - Value: `test` or `production`

**Verification:**
```bash
aws ssm get-parameters-by-path --path /uh-groupings --recursive
aws ssm get-parameter --name /uh-groupings/api/environment
```

---

## Phase 5: Container Registry

### 5.1 Create ECR Repositories

**Tasks:**
1. Create ECR Repository for API:
   - Name: `uh-groupings-api`
   - Image tag mutability: Immutable
   - Image scan on push: Enabled
   - Enable lifecycle policy to keep last 10 images

2. Create ECR Repository for UI:
   - Name: `uh-groupings-ui`
   - Image tag mutability: Immutable
   - Image scan on push: Enabled
   - Enable lifecycle policy to keep last 10 images

3. Configure repository lifecycle policies:
   ```json
   {
     "rules": [
       {
         "rulePriority": 1,
         "description": "Keep last 10 images",
         "selection": {
           "tagStatus": "any",
           "countType": "imageCountMoreThan",
           "countNumber": 10
         },
         "action": {
           "type": "expire"
         }
       }
     ]
   }
   ```

4. Create IAM policy for GitHub Actions to push images:
   - Policy name: `uh-groupings-ecr-push-policy`
   - Allow ECR push for both repositories
   - Allow ECR image scanning

5. Create IAM user for GitHub Actions (if using basic auth):
   - Name: `github-actions-uh-groupings`
   - Attach: `uh-groupings-ecr-push-policy`
   - Generate access keys

**Verification:**
```bash
aws ecr describe-repositories --repository-names uh-groupings-api uh-groupings-ui
aws ecr get-authorization-token
```

---

## Phase 6: Load Balancing

### 6.1 Create Application Load Balancer

**Tasks:**
1. Create ALB:
   - Name: `uh-groupings-alb`
   - Scheme: Internet-facing
   - IP address type: IPv4
   - VPC: uh-groupings-vpc
   - Subnets: Public Subnet 1a, Public Subnet 1b
   - Security groups: uh-groupings-alb-sg
   - Logging: Enable and send to S3 bucket (create bucket first)

2. Create Target Group for API:
   - Name: `uh-groupings-api-tg`
   - Protocol: HTTP
   - Port: 8080
   - VPC: uh-groupings-vpc
   - Target type: IP
   - Health check: /health
   - Health check interval: 30 seconds
   - Health check timeout: 5 seconds
   - Healthy threshold: 2
   - Unhealthy threshold: 3

3. Create Target Group for UI:
   - Name: `uh-groupings-ui-tg`
   - Protocol: HTTP
   - Port: 3000
   - VPC: uh-groupings-vpc
   - Target type: IP
   - Health check: /
   - Health check interval: 30 seconds
   - Health check timeout: 5 seconds
   - Healthy threshold: 2
   - Unhealthy threshold: 3

4. Create Listener:
   - Protocol: HTTP (for now, add HTTPS with certificates later)
   - Port: 80
   - Default action: Fixed response (404) or forward to rule-based routing

5. Create Listener Rules:
   - Rule 1: Path `/api/*` → Forward to uh-groupings-api-tg
   - Rule 2: Path `/*` → Forward to uh-groupings-ui-tg

6. (Optional) Add HTTPS:
   - Request SSL certificate in ACM
   - Add HTTPS listener (443)
   - Redirect HTTP (80) to HTTPS (443)

**Verification:**
```bash
aws elbv2 describe-load-balancers --names uh-groupings-alb
aws elbv2 describe-target-groups --load-balancer-arn <alb-arn>
```

### 6.2 Create S3 Bucket for ALB Logs

**Tasks:**
1. Create S3 bucket:
   - Name: `uh-groupings-alb-logs-<account-id>` (must be globally unique)
   - Block all public access: Enabled
   - Versioning: Enabled (optional)

2. Create bucket policy to allow ALB logging:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Principal": {
           "AWS": "arn:aws:iam::<elb-account-id>:root"
         },
         "Action": "s3:PutObject",
         "Resource": "arn:aws:s3:::uh-groupings-alb-logs-*/*"
       }
     ]
   }
   ```
   Note: Replace `<elb-account-id>` with the AWS account ID for ALB logging in your region

3. Enable lifecycle policy on bucket:
   - Transition to Glacier: 90 days
   - Expiration: 365 days

**Verification:**
```bash
aws s3api head-bucket --bucket uh-groupings-alb-logs-<account-id>
```

---

## Phase 7: ECS Setup

### 7.1 Create ECS Cluster

**Tasks:**
1. Create ECS Cluster:
   - Name: `uh-groupings-cluster`
   - Infrastructure: AWS Fargate (serverless)
   - Logging: CloudWatch Container Insights enabled
   - Default capacity provider: FARGATE

2. Configure CloudWatch namespace:
   - Namespace: `/ecs/uh-groupings`

**Verification:**
```bash
aws ecs describe-clusters --clusters uh-groupings-cluster
```

### 7.2 Create CloudWatch Log Groups

**Tasks:**
1. Create log group for API service:
   - Name: `/ecs/uh-groupings/api`
   - Retention: 7 days (adjustable)

2. Create log group for UI service:
   - Name: `/ecs/uh-groupings/ui`
   - Retention: 7 days (adjustable)

3. Create log group for ALB:
   - Name: `/aws/alb/uh-groupings`
   - Retention: 7 days (adjustable)

**Verification:**
```bash
aws logs describe-log-groups --log-group-name-prefix /ecs/uh-groupings
```

### 7.3 Create ECS Task Definition for API

**Tasks:**
1. Create task definition:
   - Name: `uh-groupings-api-task`
   - Launch type: FARGATE
   - Task role: uh-groupings-ecs-task-role
   - Task execution role: uh-groupings-ecs-task-execution-role
   - Operating system family: Linux
   - CPU: 512 (.5 vCPU)
   - Memory: 1024 MB (1 GB)
   - Network mode: awsvpc (required for Fargate)

2. Add container definition:
   - Container name: `api`
   - Image: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/uh-groupings-api:release-prod`
   - Port: 8080
   - CPU: 512
   - Memory: 1024
   - Essential: Yes

3. Configure container environment:
   - Mount secrets from Secrets Manager:
     - Name: `DB_HOST` → From `uh-groupings/database/connection:host`
     - Name: `DB_PORT` → From `uh-groupings/database/connection:port`
     - Name: `DB_NAME` → From `uh_groupings/database/connection:database`
     - Name: `DB_USER` → From `uh_groupings/database/connection:username`
     - Name: `DB_PASSWORD` → From `uh_groupings/database/connection:password`
     - Name: `REDIS_HOST` → From `uh-groupings/redis/connection:host`
     - Name: `REDIS_PORT` → From `uh-groupings/redis/connection:port`
     - Name: `API_KEY` → From `uh-groupings/api/secrets:api_key`
     - Name: `JWT_SECRET` → From `uh-groupings/api/secrets:jwt_secret`

   - Load parameters from Parameter Store:
     - Name: `ENVIRONMENT` → From `/uh-groupings/api/environment`
     - Name: `LOG_LEVEL` → From `/uh-groupings/api/log_level`
     - Name: `PORT` → From `/uh-groupings/api/port`
     - Name: `GROUPINGS_SERVICE_URL` → From `/uh-groupings/api/groupings_service_url`
     - Name: `SESSION_TIMEOUT` → From `/uh_groupings/api/session_timeout`

4. Configure logging:
   - Log driver: awslogs
   - Log group: `/ecs/uh-groupings/api`
   - Log stream prefix: `api/`
   - Region: us-east-1

5. Configure EFS mount for log persistence:
   - EFS file system: uh-groupings-logs-efs
   - Source path: `/api`
   - Container path: `/var/log/application/api`
   - Read-only: false
   - This allows services to write logs to shared EFS storage that persists across task replacements

6. Set up health check:
   - Command: `CMD-SHELL,curl -f http://localhost:8080/health || exit 1`
   - Interval: 30 seconds
   - Timeout: 5 seconds
   - Start period: 60 seconds
   - Retries: 3

**Verification:**
```bash
aws ecs describe-task-definition --task-definition uh-groupings-api-task
```

### 7.4 Create ECS Task Definition for UI

**Tasks:**
1. Create task definition:
   - Name: `uh-groupings-ui-task`
   - Launch type: FARGATE
   - Task role: uh-groupings-ecs-task-role
   - Task execution role: uh-groupings-ecs-task-execution-role
   - Operating system family: Linux
   - CPU: 256 (.25 vCPU)
   - Memory: 512 MB
   - Network mode: awsvpc (required for Fargate)

2. Add container definition:
   - Container name: `ui`
   - Image: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/uh-groupings-ui:release-prod`
   - Port: 3000
   - CPU: 256
   - Memory: 512
   - Essential: Yes

3. Configure container environment:
   - Load parameters from Parameter Store:
     - Name: `ENVIRONMENT` → From `/uh-groupings/ui/environment`
     - Name: `PORT` → From `/uh-groupings/ui/port`
     - Name: `API_BASE_URL` → From `/uh-groupings/ui/api_base_url`
     - Name: `LOG_LEVEL` → From `/uh_groupings/ui/log_level`

   - Mount secrets (if using OAuth):
     - Name: `OAUTH_CLIENT_ID` → From `uh-groupings/ui/secrets:oauth_client_id`
     - Name: `OAUTH_CLIENT_SECRET` → From `uh-groupings/ui/secrets:oauth_client_secret`

4. Configure logging:
   - Log driver: awslogs
   - Log group: `/ecs/uh-groupings/ui`
   - Log stream prefix: `ui/`
   - Region: us-east-1

5. Configure EFS mount for log persistence:
   - EFS file system: uh-groupings-logs-efs
   - Source path: `/ui`
   - Container path: `/var/log/application/ui`
   - Read-only: false
   - This allows the UI service to write logs to shared EFS storage that persists across task replacements

6. Set up health check:
   - Command: `CMD-SHELL,curl -f http://localhost:3000/ || exit 1`
   - Interval: 30 seconds
   - Timeout: 5 seconds
   - Start period: 60 seconds
   - Retries: 3

**Verification:**
```bash
aws ecs describe-task-definition --task-definition uh-groupings-ui-task
```

### 7.5 Create ECS Service for API

**Tasks:**
1. Create service:
   - Name: `uh-groupings-api-service`
   - Cluster: uh-groupings-cluster
   - Task definition: uh-groupings-api-task:1
   - Launch type: FARGATE
   - Desired count: 2

2. Configure networking:
   - VPC: uh-groupings-vpc
   - Subnets: Private Subnet 1a, Private Subnet 1b
   - Security groups: uh-groupings-ecs-sg
   - Public IP: DISABLED
   - Assign public IP: DISABLED

3. Load balancing:
   - Load balancer type: Application Load Balancer
   - Load balancer: uh-groupings-alb
   - Target group: uh-groupings-api-tg
   - Container: api:8080
   - Protocol: HTTP

4. Auto-scaling:
   - Desired count: 2
   - Minimum: 1
   - Maximum: 4
   - Target CPU utilization: 70%
   - Target memory utilization: 80%

5. Deployment configuration:
   - Deployment type: Rolling update
   - Maximum percent: 200%
   - Minimum healthy percent: 100%

**Verification:**
```bash
aws ecs describe-services --cluster uh-groupings-cluster --services uh-groupings-api-service
```

### 7.6 Create ECS Service for UI

**Tasks:**
1. Create service:
   - Name: `uh-groupings-ui-service`
   - Cluster: uh-groupings-cluster
   - Task definition: uh-groupings-ui-task:1
   - Launch type: FARGATE
   - Desired count: 2

2. Configure networking:
   - VPC: uh-groupings-vpc
   - Subnets: Private Subnet 1a, Private Subnet 1b
   - Security groups: uh-groupings-ecs-sg
   - Public IP: DISABLED
   - Assign public IP: DISABLED

3. Load balancing:
   - Load balancer type: Application Load Balancer
   - Load balancer: uh-groupings-alb
   - Target group: uh-groupings-ui-tg
   - Container: ui:3000
   - Protocol: HTTP

4. Auto-scaling:
   - Desired count: 2
   - Minimum: 1
   - Maximum: 4
   - Target CPU utilization: 70%
   - Target memory utilization: 80%

5. Deployment configuration:
   - Deployment type: Rolling update
   - Maximum percent: 200%
   - Minimum healthy percent: 100%

**Verification:**
```bash
aws ecs describe-services --cluster uh-groupings-cluster --services uh-groupings-ui-service
```

---

## Phase 8: Monitoring and Logging

### 8.1 Create CloudWatch Alarms

**Tasks:**
1. Create API Service Alarms:
   - Alarm name: `uh-groupings-api-cpu-utilization`
   - Metric: ECS service CPU utilization
   - Threshold: > 80%
   - Evaluation period: 1 minute
   - Action: SNS notification to ops team

   - Alarm name: `uh-groupings-api-memory-utilization`
   - Metric: ECS service memory utilization
   - Threshold: > 85%
   - Evaluation period: 1 minute
   - Action: SNS notification to ops team

   - Alarm name: `uh-groupings-api-task-count`
   - Metric: ECS service running task count
   - Threshold: < desired count
   - Evaluation period: 2 minutes
   - Action: SNS notification to ops team

2. Create UI Service Alarms:
   - Same metrics as API service with appropriate thresholds

3. Create ALB Alarms:
   - Alarm name: `uh-groupings-alb-unhealthy-hosts`
   - Metric: Target Group unhealthy host count
   - Threshold: > 0
   - Action: SNS notification

   - Alarm name: `uh-groupings-alb-target-response-time`
   - Metric: Target response time
   - Threshold: > 2 seconds
   - Action: SNS notification

4. Create RDS Alarms:
   - Alarm name: `uh-groupings-rds-cpu-utilization`
   - Threshold: > 80%

   - Alarm name: `uh-groupings-rds-db-connections`
   - Threshold: > 80 (or configurable)

   - Alarm name: `uh-groupings-rds-storage-space`
   - Threshold: < 10 GB free

5. Create ElastiCache Alarms:
   - Alarm name: `uh-groupings-redis-cpu-utilization`
   - Threshold: > 80%

   - Alarm name: `uh-groupings-redis-evictions`
   - Threshold: > 0 (any eviction indicates need for larger cache)

**Verification:**
```bash
aws cloudwatch describe-alarms --alarm-names uh-groupings-api-cpu-utilization
```

### 8.2 Create SNS Topic for Notifications

**Tasks:**
1. Create SNS topic:
   - Name: `uh-groupings-ops-alerts`
   - Display name: "UH Groupings Operations Alerts"

2. Create email subscription:
   - Endpoint: ops-team@hawaii.edu
   - Protocol: Email

3. Create Slack webhook subscription (if using Slack):
   - Use SNS integration with Slack

4. Create SMS subscription (for critical alerts, if needed):
   - Endpoint: +1-XXX-XXX-XXXX
   - Protocol: SMS

**Verification:**
```bash
aws sns list-subscriptions-by-topic --topic-arn <topic-arn>
```

### 8.3 Create CloudWatch Dashboards

**Tasks:**
1. Create main dashboard "uh-groupings-main":
   - API Service metrics (CPU, memory, task count)
   - UI Service metrics (CPU, memory, task count)
   - ALB metrics (request count, response time, unhealthy hosts)
   - RDS metrics (connections, CPU, storage)
   - ElastiCache metrics (hits, misses, evictions)

2. Create API Service dashboard "uh-groupings-api-detail":
   - Request metrics
   - Error rates
   - Latency percentiles
   - Task distribution across AZs

3. Create Database dashboard "uh-groupings-database":
   - RDS performance insights
   - Query performance
   - Connection pooling status
   - Replication lag

**Verification:**
```bash
aws cloudwatch describe-dashboards --dashboard-name-prefix uh-groupings
```

---

## Phase 9: Deployment Workflows

### 9.1 Create GitHub Actions Secrets

**Tasks:**
1. In the `uh-groupings-api` repository:
   - Go to Settings → Secrets and variables → Actions
   - Create secret: `AWS_ACCESS_KEY_ID` (from GitHub Actions IAM user)
   - Create secret: `AWS_SECRET_ACCESS_KEY` (from GitHub Actions IAM user)
   - Create secret: `AWS_ACCOUNT_ID` (your AWS account ID)
   - Create secret: `ECR_REPOSITORY_NAME` (uh-groupings-api)
   - Create secret: `AWS_REGION` (us-east-1)

2. In the `uh_groupings-ui` repository:
   - Same secrets as API repo with `ECR_REPOSITORY_NAME` = uh-groupings-ui

3. In the `example-aws-iac` repository:
   - Create secret: `AWS_ACCESS_KEY_ID` (from infrastructure IAM user)
   - Create secret: `AWS_SECRET_ACCESS_KEY` (from infrastructure IAM user)
   - Create secret: `AWS_ACCOUNT_ID`
   - Create secret: `AWS_REGION`

**Verification:**
```bash
gh secret list --repo uhawaii-system-its-ti-iam/uh_groupings-api
```

### 9.2 Configure Service Repository Workflows

**Tasks:**
1. In `uh_groupings-api` repository, create `.github/workflows/build-and-push.yml`:
   - Trigger: on push to `release-prod` branch
   - Jobs:
     - Build Docker image
     - Push to ECR with tag `release-prod`
     - Run image security scan

2. In `uh_groupings-ui` repository, create `.github/workflows/build-and-push.yml`:
   - Same structure as API

### 9.3 Configure Infrastructure Repository Workflows

**Tasks:**
1. Test Environment Workflow (`.github/workflows/deploy-test.yml`):
   - Trigger: on push to `release-prod` branch of service repos (webhook) or manual trigger
   - Steps:
     - Checkout code
     - Setup CDK environment
     - CDK synth
     - CDK deploy to test environment
     - Run smoke tests against test environment
     - Send notification with test environment URL

2. Production Environment Workflow (`.github/workflows/deploy-prod.yml`):
   - Trigger: manual via GitHub Actions UI
   - Steps:
     - Checkout code
     - Setup CDK environment
     - Show what will be deployed (CDK diff)
     - Require manual approval
     - CDK deploy to production
     - Run smoke tests against production
     - Send notification with production URL

**Verification:**
```bash
gh workflow list --repo uhawaii-system-its-ti-iam/example-aws-iac
```

---

## Phase 10: Testing and Validation

### 10.1 Test Networking

**Tasks:**
1. Test VPC connectivity:
   - Launch EC2 instance in public subnet
   - SSH into instance
   - Test connectivity to private subnets
   - Test NAT Gateway egress
   - Clean up test instance

2. Test security group rules:
   - Verify ALB can reach ECS tasks
   - Verify ECS tasks can reach RDS
   - Verify ECS tasks can reach ElastiCache
   - Verify RDS can't be reached from internet

**Commands:**
```bash
# From EC2 instance in public subnet
ping 10.0.10.1  # Private subnet
curl http://10.0.10.5:8080/health  # ECS task
```

### 10.2 Test Database

**Tasks:**
1. Connect to RDS from ECS task:
   - Verify connection string from Secrets Manager
   - Test basic SQL query
   - Test read/write operations
   - Check replication lag (if Multi-AZ)

2. Test backup and restore:
   - Trigger manual backup
   - Verify backup exists
   - (Optional) Test restore to new instance

**Commands:**
```bash
# From ECS task or local with port forwarding
psql -h <rds-endpoint> -U dbadmin -d uh_groupings_db -c "SELECT 1;"
```

### 10.3 Test ElastiCache

**Tasks:**
1. Connect to Redis from ECS task:
   - Verify connection string from Secrets Manager
   - Test SET/GET operations
   - Verify cluster has 2 nodes

2. Test failover:
   - Trigger failover between nodes
   - Verify service stays online
   - Check failover logs

**Commands:**
```bash
# From ECS task
redis-cli -h <cache-endpoint> -p 6379 ping
redis-cli -h <cache-endpoint> -p 6379 SET test_key "value"
redis-cli -h <cache-endpoint> -p 6379 GET test_key
```

### 10.4 Test Load Balancer

**Tasks:**
1. Test ALB routing:
   - Hit ALB URL for API endpoint: `curl <alb-url>/api/health`
   - Hit ALB URL for UI endpoint: `curl <alb-url>/`
   - Verify requests reach correct target groups

2. Test health checks:
   - Verify targets are healthy in target groups
   - Temporarily stop one task
   - Verify ALB removes unhealthy target
   - Verify ECS launches new task
   - Verify ALB adds new task to rotation

3. Test HTTPS (if configured):
   - Verify SSL certificate is valid
   - Test HTTPS endpoints
   - Verify HTTP redirects to HTTPS

**Commands:**
```bash
curl -v http://<alb-dns>/api/health
curl -v http://<alb-dns>/
aws elbv2 describe-target-health --target-group-arn <tg-arn>
```

### 10.5 Test ECS Services

**Tasks:**
1. Verify services are running:
   - Check task count matches desired count
   - Check all tasks are in RUNNING state
   - Verify CPU/memory allocation

2. Test auto-scaling:
   - Generate load on service
   - Verify task count increases
   - Verify new tasks reach healthy state
   - Remove load
   - Verify task count decreases after cooldown

3. Test task placement:
   - Verify tasks are distributed across AZs
   - Verify proper fault tolerance

**Commands:**
```bash
aws ecs describe-services --cluster uh-groupings-cluster --services uh-groupings-api-service
aws ecs list-tasks --cluster uh_groupings-cluster --service-name uh-groupings-api-service
aws ecs describe-tasks --cluster uh_groupings-cluster --tasks <task-arn>
```

### 10.6 Test Secrets and Parameters

**Tasks:**
1. Verify ECS tasks can access secrets:
   - Log into ECS task
   - Verify environment variables are set from Secrets Manager
   - Test database connectivity with credentials from secret

2. Verify ECS tasks can access parameters:
   - Log into ECS task
   - Verify environment variables are set from Parameter Store
   - Verify correct configuration values are injected

3. Test secret rotation:
   - Rotate a secret manually
   - Verify new secret is used (may require task restart)
   - Verify old secret is deprecated

**Commands:**
```bash
# From CloudWatch Logs or ECS task shell
echo $DB_PASSWORD
echo $ENVIRONMENT
aws ssm get-parameter --name /uh-groupings/api/environment
```

### 10.7 Test Monitoring and Alarms

**Tasks:**
1. Verify CloudWatch metrics are being collected:
   - Check ECS service metrics
   - Check ALB metrics
   - Check RDS metrics
   - Check ElastiCache metrics

2. Test alarms:
   - Trigger CPU alarm by generating load
   - Verify alarm state changes to ALARM
   - Verify SNS notification is received
   - Verify logs show alarm trigger

3. Verify CloudWatch dashboards:
   - Open main dashboard
   - Verify all metrics are displayed
   - Verify no missing data points

**Commands:**
```bash
aws cloudwatch get-metric-statistics --namespace AWS/ECS --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=uh-groupings-api-service --start-time 2024-01-01 --end-time 2024-01-02 --period 300 --statistics Average
```

---

## Phase 11: Documentation and Handoff

### 11.1 Create Runbooks

**Tasks:**
1. Create runbook for common operations:
   - Scaling services up/down
   - Updating service images
   - Rolling back deployments
   - Restarting failed tasks
   - Accessing logs
   - Accessing database
   - Clearing cache
   - Emergency procedures

2. Create troubleshooting guide:
   - Common error messages
   - Debugging steps
   - Contact information for escalation

### 11.2 Create Disaster Recovery Plan

**Tasks:**
1. Document backup and recovery procedures:
   - RDS backup schedule and retention
   - Recovery time objectives (RTO)
   - Recovery point objectives (RPO)
   - Step-by-step recovery procedures

2. Document failover procedures:
   - Multi-AZ failover
   - Manual failover steps
   - Testing failover scenario

### 11.3 Create Documentation

**Tasks:**
1. Document all AWS resource IDs and names
2. Document IP ranges and security group rules
3. Document parameter and secret naming conventions
4. Document monitoring dashboard URLs
5. Document team access and permissions

---

## Verification Checklist

Use this checklist to verify all components are properly set up:

- [ ] VPC with 4 subnets in 2 AZs
- [ ] Internet Gateway attached to VPC
- [ ] NAT Gateways in public subnets
- [ ] Route tables configured for public/private subnets
- [ ] Security groups for ALB, ECS, RDS, and ElastiCache
- [ ] RDS PostgreSQL instance running in private subnets
- [ ] ElastiCache Redis cluster running in private subnets
- [ ] ECR repositories created for API and UI
- [ ] ALB created with target groups and listeners
- [ ] ECS cluster created
- [ ] CloudWatch log groups created
- [ ] ECS task definitions created for API and UI
- [ ] ECS services created with desired task count
- [ ] Load balancer is responding to requests
- [ ] Database is accessible from ECS tasks
- [ ] Cache is accessible from ECS tasks
- [ ] Secrets are injected into ECS tasks
- [ ] Parameters are injected into ECS tasks
- [ ] CloudWatch alarms are configured
- [ ] SNS topic is configured for notifications
- [ ] GitHub Actions secrets are configured
- [ ] Service build workflows are working
- [ ] All tests pass

---

## Cost Optimization Tips

- Use smaller instance types (t3.micro/t3.small) for non-production environments
- Enable resource tagging for cost allocation
- Use Reserved Instances for predictable workloads
- Set up budget alerts in AWS Billing
- Review unused resources regularly
- Use spot instances for batch processing (if applicable)
- Enable S3 lifecycle policies for log retention

---

## Security Best Practices

- Enable MFA for all AWS accounts
- Use IAM roles instead of access keys where possible
- Regularly rotate secrets
- Enable CloudTrail for audit logging
- Use VPC endpoints for AWS services instead of internet gateway
- Enable VPC Flow Logs
- Use security groups as firewalls
- Enable RDS encryption at rest
- Enable ECS task role for least privilege access
- Regularly scan ECR images for vulnerabilities
- Enable AWS Config for compliance monitoring

---

## Next Steps

1. Follow each phase sequentially
2. Verify each phase before moving to the next
3. Test thoroughly in a test environment before production
4. Document any deviations from this guide
5. Keep AWS credentials secure
6. Monitor costs and resources regularly
7. Plan capacity for future growth

