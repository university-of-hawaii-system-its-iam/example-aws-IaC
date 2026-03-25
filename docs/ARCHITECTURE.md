# Architecture Documentation

This directory contains architecture diagrams and documentation for the infrastructure deployment.

## Multi-Repository Architecture

This project uses a **polyrepo architecture** where infrastructure and services are separated across repositories:

### Repositories

1. **example-aws-iac** (Infrastructure - This Repository)
   - AWS CDK infrastructure code
   - Deployment automation
   - References to external service images

2. **uh-groupings-api** (API Service)
   - https://github.com/uhawaii-system-its-ti-iam/uh-groupings-api/tree/release-prod
   - API source code
   - Dockerfile and build pipeline
   - Publishes images to AWS ECR

3. **uh-groupings-ui** (UI Service)
   - https://github.com/uhawaii-system-its-ti-iam/uh-groupings-ui/tree/release-prod
   - React UI source code
   - Dockerfile and build pipeline
   - Publishes images to AWS ECR

## Infrastructure Stack Composition

### Network Stack (`network-stack.ts`)
Defines networking infrastructure:
- **VPC** - Virtual Private Cloud with configurable CIDR
- **Public Subnets** - For load balancer and NAT Gateway
- **Private Subnets** - For ECS tasks and databases
- **Internet Gateway** - For internet connectivity
- **NAT Gateway** - For outbound traffic from private subnets
- **Route Tables** - For routing between subnets
- **Security Groups** - For network access control
- **Network ACLs** - Additional network segmentation

### Data Stack (`data-stack.ts`)
Defines data and storage infrastructure:
- **RDS PostgreSQL** - Managed relational database
  - PostgreSQL 15.x
  - Multi-AZ for high availability
  - Automated backups (7 days)
  - For application data persistence
- **ElastiCache** - In-memory caching
  - Redis cluster with Multi-AZ failover
  - For session storage and caching
- **Amazon EFS** - Persistent file storage for logs
  - Shared file system across ECS tasks
  - Mounted to `/var/log/application` in containers
  - API logs: `/var/log/application/api/`
  - UI logs: `/var/log/application/ui/`
  - Multi-AZ mount targets for high availability
  - Automatic backup via EFS snapshots (optional)
- **Secrets Manager** - Credential management
  - API keys, database passwords, tokens
  - Automatic rotation support
- **Parameter Store** - Configuration management
  - Environment-specific settings
  - Service URLs and timeouts

### Log Persistence Strategy

**Log Files (EFS):**
- Each service writes logs to EFS mounted path
- Logs persist across task replacements and deployments
- Multi-AZ mount targets ensure availability
- CloudWatch still aggregates logs for real-time monitoring
- EFS snapshots provide point-in-time recovery
- Lifecycle policies can archive old logs to S3

**Log Aggregation (CloudWatch):**
- ECS task logs sent to CloudWatch Logs
- Real-time monitoring and alarms
- Short-term retention (7 days)
- Useful for debugging active issues

**Log Archival (S3):**
- Option to export CloudWatch logs to S3
- Long-term retention and compliance
- Cost-effective storage for audit trails

### Application Stack (`app-stack.ts`)
Defines application infrastructure:
- **ECS Cluster** - Container orchestration cluster
  - EC2 or Fargate launch type
  - Auto-scaling capability
- **ECS Task Definitions** - Service blueprints
  - Container image specification
  - Resource allocation (CPU, memory)
  - Environment variables and secrets
  - Logging configuration
- **ECS Services** - Running instances
  - API service (from `uh-groupings-api` ECR image)
  - UI service (from `uh-groupings-ui` ECR image)
  - Desired task count
  - Service-level auto-scaling
- **Application Load Balancer** - HTTP/HTTPS routing
  - Listener rules
  - Target groups
  - SSL/TLS certificates
  - Health checks
- **CloudWatch Logs** - Container logging
  - Centralized log aggregation
  - Log groups per service

## Deployment Flow

This project supports **two deployment environments**: Test (automatic) and Production (manual).

**Key Distinction:**
- **Test Environment**: Services automatically deployed when images are pushed to ECR
- **Production Environment**: Services manually deployed after infrastructure team review

```
┌─────────────────────────────────────────────────────────────┐
│                   Service Development                       │
└─────────────────────────────────────────────────────────────┘
         API Team              UI Team
         (uh-groupings-api)    (uh-groupings-ui)
               │                      │
               ├─ Commit code         ├─ Commit code
               │                      │
               ▼                      ▼
         GitHub Actions         GitHub Actions
         (build-push.yml)       (build-push.yml)
      [AUTOMATICALLY TRIGGERED] [AUTOMATICALLY TRIGGERED]
               │                      │
               ├─ Build image         ├─ Build image
               ├─ Run tests           ├─ Run tests
               ├─ Push to ECR         ├─ Push to ECR
               │                      │
               └──────────┬───────────┘
                          │
                          ▼
                   AWS ECR (Registry)
                  api:release-prod
                  ui:release-prod
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│  TEST ENVIRONMENT            │ │  PRODUCTION ENVIRONMENT      │
│  [AUTOMATIC DEPLOYMENT]      │ │  [MANUAL DEPLOYMENT]         │
└──────────────────────────────┘ └──────────────────────────────┘
          │                               │
          │                    Infrastructure Team
          │                    (example-aws-iac)
          │                               │
          │                    Update app-stack.ts
          │                    with ECR image URIs
          │                               │
          │                    Commit & Push to main
          │                               │
   ┌──────┴───────────────────────────────┴──────────┐
   │                                                 │
   ▼                                                 ▼
GitHub Actions                            GitHub Actions
(deploy-test.yml)                         (deploy-prod.yml)
[AUTOMATICALLY TRIGGERED]                 [AWAITING MANUAL TRIGGER]
   │                                                 │
   ├─ CDK Synth (Test)                    Infrastructure team must:
   ├─ CDK Deploy (Test)           1. Review the proposed changes
   │                              2. Manually trigger the workflow
   ▼                              3. Approve the deployment
AWS ECS Test Cluster                             │
   │                                             ▼
   ├─ Test API Service                 ┌────────────────┐
   ├─ Test UI Service                  │ CDK Synth      │
   └─ Test Load Balancer               │ (Production)   │
                                       └────────────────┘
                                             │
                                             ▼
                                       ┌────────────────┐
                                       │ CDK Deploy     │
                                       │ (Production)   │
                                       └────────────────┘
                                             │
                                             ▼
                                    AWS ECS Production Cluster
                                             │
                                       ┌─────┴─────┐
                                       │           │
                                       ▼           ▼
                              Prod API Service  Prod UI Service
                                       │           │
                                       └─────┬─────┘
                                             │
                                             ▼
                                    Production Load Balancer
```

### Workflow Trigger Types

**Service Build & Push Workflows** (Automatic)
- Triggered on: Commit/push to `release-prod` branch in service repositories
- Runs: Build, test, and push Docker image to ECR
- No manual approval required
- Happens immediately upon code changes

**Test Environment Deployment Workflow** (Automatic)
- Triggered on: New images pushed to ECR (by service team CI/CD)
- Status: Automatically executes when images are available
- Updates: Test ECS services with latest images
- No approval required
- Purpose: Enables continuous testing with latest builds
- Image tags: `api:release-prod`, `ui:release-prod` (same as prod, but deployed to test environment)

**Production Environment Deployment Workflow** (Manual)
- Triggered on: Commit to `main` branch in `example-aws-iac` repository
- Status: Workflow is available but **NOT automatically executed**
- Required action: Infrastructure team must manually trigger the workflow
- Approval: May require environment approval depending on branch protection settings
- Purpose: Prevents accidental deployments and ensures controlled releases to production
- Image tags: Must be explicitly specified in `app-stack.ts` (allows pinning to specific versions)

## Service Integration Points

### Image References
- **API Image**: `<ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/uh-groupings-api:release-prod`
- **UI Image**: `<ACCOUNT>.dkr.ecr.<REGION>.amazonaws.com/uh-groupings-ui:release-prod`

### Environment Configuration
Services receive configuration via:
- **Environment Variables** - Set in task definition
- **Secrets Manager** - For sensitive data (database passwords, API keys)
- **Parameter Store** - For non-sensitive configuration

### Cross-Service Communication
- **API Service** - Internal port (typically 8080 or 3000)
- **UI Service** - Port 3000 (front-facing through ALB)
- **Load Balancer** - Routes requests to services
  - Path-based routing: `/api/*` → API service
  - Root path `/` → UI service

## Deployment Considerations

### Blue-Green Deployment
- ECS services support task replacement
- New images deployed without downtime
- Previous tasks terminated after health checks pass

### Auto-Scaling
- Task-level: Scale ECS tasks up/down based on CPU/memory
- Cluster-level: Scale EC2 instances (if using EC2 launch type)
- Application Load Balancer: Distributes traffic across tasks

### Health Checks
- **ALB Health Checks**: Verify service is responding
- **ECS Health Checks**: Monitor container status
- **CloudWatch**: Alarms on service metrics

### Logging and Monitoring
- CloudWatch Logs: Container stdout/stderr
- CloudWatch Metrics: ECS, ALB, RDS metrics
- CloudWatch Alarms: Automated alerts

## Contents

- **diagrams/** - Architecture diagrams (add C4 model, network topology, etc.)
- **decisions/** - Architecture Decision Records (ADRs)
- **guides/** - Implementation guides and runbooks

## Next Steps

1. ✅ Define infrastructure stacks
2. ✅ Document deployment flow
3. ⏳ Create detailed architecture diagrams
4. ⏳ Document architecture decisions (ADRs)
5. ⏳ Create runbooks for common operations
