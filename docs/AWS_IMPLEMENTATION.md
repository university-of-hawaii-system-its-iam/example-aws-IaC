# AWS Implementation Plan - Log Rotation & Archival

## High-Level Overview

This document provides a comprehensive implementation plan for deploying the log rotation and archival system on AWS for the UH Groupings ECS Fargate deployment. The system consists of three tiers designed to balance performance, cost, and compliance requirements.

### System Architecture at a Glance

```
┌─────────────────────────┐
│   ECS Fargate Tasks     │
│  (API & UI Services)    │
└────────────┬────────────┘
             │
      ┌──────┴──────┐
      │             │
      ↓             ↓
┌──────────────┐  ┌──────────────────────┐
│  Local Logs  │  │  Container STDOUT    │
│  (EFS)       │  │  (Log Streaming)     │
│  30 days     │  │                      │
└──────────────┘  └──────────┬───────────┘
                             │
                             ↓
                   ┌──────────────────────┐
                   │  CloudWatch Logs     │
                   │  7 days retention    │
                   │  Queryable & Alarmed │
                   └──────────┬───────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ↓                   ↓
             ┌────────────────┐  ┌──────────────────┐
             │  Real-time     │  │  S3 Archival     │
             │  Monitoring    │  │  (via Lambda)    │
             │  & Debugging   │  │  7 years         │
             └────────────────┘  └──────────────────┘
```

### Three-Tier System Benefits

| Tier | Technology | Use Case | Cost | Retention |
|------|-----------|----------|------|-----------|
| **Tier 1** | EFS (Local) | Immediate troubleshooting, fast access | $0.30/GB/mo | 30 days |
| **Tier 2** | CloudWatch | Real-time monitoring, alerting, queries | $0.50/GB ingested | 7 days |
| **Tier 3** | S3 + Lifecycle | Compliance, long-term audit trail, cost-optimized storage | ~$0.001/GB/mo | 7 years |

### Key Features

- ✅ Automatic log rotation every 6 hours with daily triggers
- ✅ Automatic compression (gzip) of old logs
- ✅ Real-time log aggregation via CloudWatch
- ✅ Automated daily export to S3
- ✅ Cost-optimized storage with lifecycle transitions
- ✅ 7-year compliance retention window
- ✅ Production-ready with monitoring and alarms
- ✅ Zero application code changes required

### Prerequisites

Before starting, the following must be in place. Items marked with *(TODO)* are
defined in the CDK stacks but not yet implemented:

- AWS Account with CDK bootstrap completed (`cdk bootstrap`)
- AWS CLI v2 installed and configured
- Python 3.9+ and pip installed
- CDK CLI installed (`npm install -g aws-cdk`)
- Docker installed locally for testing
- **VPC with public/private subnets** — defined in `NetworkStack` *(TODO)*
- **ECS Cluster** — defined in `AppStack` *(TODO)*
- **EFS File System** with mount targets in private subnets — to be added to `DataStack` *(TODO)*
- **ECR repositories** for `uh-groupings-api` and `uh-groupings-ui`
- GitHub repository access for CI/CD workflows

> **Note:** The CDK stacks in `infra/stacks/` contain TODO placeholders for VPC,
> ECS, and EFS resources. These must be implemented before the log rotation
> infrastructure can be deployed. This plan assumes those are completed first
> or are being done in parallel.

---

## Detailed Implementation Plan

### Phase 1: Planning & Preparation (Week 1)

#### 1.1 Requirements Review
**Goal:** Ensure all stakeholders understand the system and requirements

**Tasks:**
- [ ] Review this implementation plan with team
- [ ] Identify log volume for each service (API, UI)
- [ ] Determine compliance retention window (default: 7 years)
- [ ] Establish cost budget for logging infrastructure
- [ ] Document any custom log formats or requirements
- [ ] Get approval from infrastructure and security teams

**Deliverables:**
- [ ] Signed-off requirements document
- [ ] Estimated monthly cost projection
- [ ] Risk assessment document
- [ ] Rollback plan approved

**Success Criteria:**
- All team members understand the three-tier approach
- Cost is within budget expectations
- Compliance requirements are met by the design

---

#### 1.2 Environment Audit
**Goal:** Understand current infrastructure and identify gaps

**Tasks:**
- [ ] Audit current ECS cluster configuration
- [ ] Verify EFS filesystem exists and is accessible from ECS tasks
- [ ] Check ECS task definition log driver configuration
- [ ] Review IAM roles and permissions
- [ ] Verify S3 bucket naming conventions
- [ ] Test network connectivity (ECS → EFS, ECS → CloudWatch, Lambda → S3)

**Audit Checklist:**
```bash
# Check EFS
aws efs describe-file-systems \
  --query 'FileSystems[?Tags[?Key==`Name` && Value==`uh-groupings-logs`]]'

# Check ECS cluster
aws ecs describe-clusters \
  --clusters uh-groupings-cluster \
  --query 'clusters[0]'

# Check IAM roles
aws iam get-role --role-name ecsTaskExecutionRole

# Check existing CloudWatch log groups
aws logs describe-log-groups \
  --query 'logGroups[?contains(logGroupName, `uh-groupings`)]'

# Check existing S3 buckets
aws s3api list-buckets \
  --query 'Buckets[?contains(Name, `uh-groupings`)]'
```

**Deliverables:**
- [ ] Infrastructure audit report
- [ ] Gap analysis document
- [ ] List of required IAM permissions
- [ ] Network connectivity verification

**Success Criteria:**
- EFS filesystem is accessible from ECS tasks
- IAM roles exist and have required permissions
- No critical gaps identified

---

### Phase 2: Infrastructure Setup (Week 2)

#### 2.1 Deploy the LogArchivalStack
**Goal:** Deploy the S3 bucket, CloudWatch log groups, Lambda export function,
and EventBridge schedule — all defined in the existing
`infra/stacks/log_archival_stack.py`.

**Reference file:** `infra/stacks/log_archival_stack.py`

This stack creates:
- S3 bucket (`uh-groupings-logs-archive-{account}`) with lifecycle policies
  (Glacier at 90 days, Deep Archive at 180 days, expire at 7 years)
- CloudWatch Log Groups (`/ecs/uh-groupings/api` and `/ecs/uh-groupings/ui`)
  with 7-day retention
- Lambda function (Python 3.11, inline code) for daily CloudWatch → S3 export
- EventBridge rule triggering the Lambda at 2 AM UTC daily

**Step 1: Register the stack in `app.py`**

The stack is already defined in `infra/stacks/log_archival_stack.py` but is not
yet registered in `infra/app.py`. Add it:

```python
# infra/app.py
from stacks.log_archival_stack import LogArchivalStack

# ...existing stacks...
LogArchivalStack(app, "LogArchivalStack", env=env)
```

**Step 2: Deploy**

```bash
cd infra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cdk synth LogArchivalStack   # Validate the template
cdk deploy LogArchivalStack  # Deploy to AWS
```

**Step 3: Verify**

```bash
# Verify S3 bucket
aws s3api head-bucket \
  --bucket uh-groupings-logs-archive-$(aws sts get-caller-identity --query Account --output text)

# Verify CloudWatch log groups
aws logs describe-log-groups \
  --log-group-name-prefix /ecs/uh-groupings/ \
  --query 'logGroups[].{Name:logGroupName, Retention:retentionInDays}'

# Verify Lambda function
aws lambda get-function \
  --function-name $(aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `export-logs`)].FunctionName' \
    --output text)

# Verify EventBridge rule
aws events list-rules \
  --query 'Rules[?contains(Name, `export-logs`)]'
```

**Deliverables:**
- [ ] `LogArchivalStack` registered in `app.py`
- [ ] Stack deployed successfully via `cdk deploy`
- [ ] S3 bucket created with versioning, encryption, public access blocked
- [ ] Lifecycle policy active (Glacier 90d → Deep Archive 180d → Expire 2555d)
- [ ] CloudWatch log groups created with 7-day retention
- [ ] Lambda function deployed and invokable
- [ ] EventBridge rule scheduled at 2 AM UTC daily

**Success Criteria:**
- `cdk deploy` completes without errors
- All resources visible in AWS Console
- Manual Lambda invocation succeeds

---

#### 2.2 Add S3 Bucket Policy for CloudWatch Logs Export

**Goal:** The CloudWatch Logs `CreateExportTask` API requires the destination
S3 bucket to have a resource policy that grants the CloudWatch Logs service
principal write access. Without this, all export tasks will fail with an
`InvalidParameterException`.

> **This is a critical step that is easy to miss.**

**Apply via AWS CLI:**

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="uh-groupings-logs-archive-${ACCOUNT_ID}"
REGION=$(aws configure get region)

aws s3api put-bucket-policy \
  --bucket "${BUCKET_NAME}" \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [
      {
        \"Effect\": \"Allow\",
        \"Principal\": {
          \"Service\": \"logs.${REGION}.amazonaws.com\"
        },
        \"Action\": \"s3:GetBucketAcl\",
        \"Resource\": \"arn:aws:s3:::${BUCKET_NAME}\",
        \"Condition\": {
          \"StringEquals\": {
            \"aws:SourceAccount\": \"${ACCOUNT_ID}\"
          }
        }
      },
      {
        \"Effect\": \"Allow\",
        \"Principal\": {
          \"Service\": \"logs.${REGION}.amazonaws.com\"
        },
        \"Action\": \"s3:PutObject\",
        \"Resource\": \"arn:aws:s3:::${BUCKET_NAME}/*\",
        \"Condition\": {
          \"StringEquals\": {
            \"s3:x-amz-acl\": \"bucket-owner-full-control\",
            \"aws:SourceAccount\": \"${ACCOUNT_ID}\"
          }
        }
      }
    ]
  }"
```

**Alternatively, add to CDK** (recommended for infrastructure-as-code):

Add to `log_archival_stack.py` after the bucket is created:

```python
self.log_archive_bucket.add_to_resource_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        principals=[iam.ServicePrincipal(f"logs.{region}.amazonaws.com")],
        actions=["s3:GetBucketAcl"],
        resources=[self.log_archive_bucket.bucket_arn],
        conditions={
            "StringEquals": {"aws:SourceAccount": account_id},
        },
    )
)

self.log_archive_bucket.add_to_resource_policy(
    iam.PolicyStatement(
        effect=iam.Effect.ALLOW,
        principals=[iam.ServicePrincipal(f"logs.{region}.amazonaws.com")],
        actions=["s3:PutObject"],
        resources=[f"{self.log_archive_bucket.bucket_arn}/*"],
        conditions={
            "StringEquals": {
                "s3:x-amz-acl": "bucket-owner-full-control",
                "aws:SourceAccount": account_id,
            },
        },
    )
)
```

**Verify:**

```bash
# Test export manually
aws lambda invoke \
  --function-name $(aws lambda list-functions \
    --query 'Functions[?contains(FunctionName, `export-logs`)].FunctionName' \
    --output text) \
  /tmp/export-response.json

cat /tmp/export-response.json
# Should show status: "PENDING" for each log group, not errors
```

**Deliverables:**
- [ ] S3 bucket policy applied
- [ ] Manual Lambda invocation produces successful export tasks

**Success Criteria:**
- `CreateExportTask` does not fail with `InvalidParameterException`
- Export task status transitions from `PENDING` to `COMPLETED`

---

### Phase 3: Service Container Updates (Week 2-3)

#### 3.1 Update API Service (uh-groupings-api)
**Goal:** Add log rotation to API container

**Location:** `uh-groupings-api` repository

**Reference files** (from this repository):
- `services/api/Dockerfile`
- `services/api/entrypoint.sh`
- `services/api/logrotate-api.conf`
- `services/api/logback-spring.xml`

**Steps:**

1. **Copy configuration files into your service repository build context:**
   ```bash
   # From the example-aws-IaC repo, copy into your uh-groupings-api repo root:
   cp services/api/entrypoint.sh       <uh-groupings-api-repo>/entrypoint.sh
   cp services/api/logrotate-api.conf  <uh-groupings-api-repo>/logrotate-api.conf
   cp services/api/logback-spring.xml  <uh-groupings-api-repo>/src/main/resources/logback-spring.xml
   chmod +x <uh-groupings-api-repo>/entrypoint.sh
   ```

2. **Update the Dockerfile runtime stage** to match `services/api/Dockerfile`:
   ```dockerfile
   # ...existing build stage...

   # Stage 2: Runtime Stage
   FROM eclipse-temurin:17-jre-alpine

   WORKDIR /app

   # Install logrotate
   RUN apk add --no-cache logrotate

   # Copy the built JAR from builder stage
   COPY --from=builder /app/target/*.jar app.jar

   # Create log and archive directories with proper permissions
   RUN mkdir -p /var/log/application/api /logs/Archive && \
       chmod 755 /var/log/application/api /logs/Archive

   # Copy logrotate configuration
   COPY logrotate-api.conf /etc/logrotate.d/api

   # Copy logback configuration (optional, for Spring Boot log rotation)
   COPY logback-spring.xml /app/logback-spring.xml

   # Copy entrypoint script for log rotation and application startup
   COPY entrypoint.sh /app/entrypoint.sh
   RUN chmod +x /app/entrypoint.sh

   EXPOSE 8080

   HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
     CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1

   ENTRYPOINT ["/app/entrypoint.sh"]
   ```

   > **Note:** The `COPY` sources (`logrotate-api.conf`, `entrypoint.sh`,
   > `logback-spring.xml`) must be relative to the Docker build context.
   > Place these files in the repository root alongside the Dockerfile, or
   > adjust paths accordingly.

3. **Add to `application.properties`** (or `application.yml`):
   ```properties
   logging.config=classpath:logback-spring.xml
   logging.file.name=/var/log/application/api/application.log
   logging.level.root=INFO
   logging.level.com.uh.groupings=DEBUG
   ```

4. **Test locally:**
   ```bash
   docker build -t uh-groupings-api:test .
   docker run --rm \
     -v /tmp/test-logs:/var/log/application \
     -v /tmp/test-archive:/logs/Archive \
     uh-groupings-api:test

   # In another terminal, verify directories are created:
   ls -la /tmp/test-logs/api/
   ls -la /tmp/test-archive/
   ```

   > **Tip:** For faster testing, temporarily change `sleep 21600` in
   > `entrypoint.sh` to `sleep 60` to trigger rotation after 1 minute.

5. **Commit and push:**
   ```bash
   git add entrypoint.sh logrotate-api.conf Dockerfile
   git add src/main/resources/logback-spring.xml
   git add src/main/resources/application.properties
   git commit -m "feat: add log rotation with archival to /logs/Archive"
   git push origin main
   ```

**Deliverables:**
- [ ] `entrypoint.sh` — copied and executable
- [ ] `logrotate-api.conf` — copied to repo root
- [ ] `logback-spring.xml` — added to `src/main/resources/`
- [ ] `Dockerfile` — updated with logrotate
- [ ] `application.properties` — logging config added
- [ ] Local Docker build and run successful
- [ ] Changes committed and pushed

**Success Criteria:**
- `docker build` completes without errors
- Container starts, creates log file at `/var/log/application/api/application.log`
- `logrotate -d -f /etc/logrotate.d/api` (dry run) reports no errors inside container
- No permission errors in container logs

---

#### 3.2 Update UI Service (uh-groupings-ui)
**Goal:** Add log rotation to UI container

**Location:** `uh-groupings-ui` repository

**Reference files** (from this repository):
- `services/ui/Dockerfile`
- `services/ui/entrypoint.sh`
- `services/ui/logrotate-ui.conf`
- `services/ui/logback-spring.xml`

**Steps:** Same as Phase 3.1, but with UI-specific paths:

1. **Copy configuration files:**
   ```bash
   cp services/ui/entrypoint.sh       <uh-groupings-ui-repo>/entrypoint.sh
   cp services/ui/logrotate-ui.conf   <uh-groupings-ui-repo>/logrotate-ui.conf
   cp services/ui/logback-spring.xml  <uh-groupings-ui-repo>/src/main/resources/logback-spring.xml
   chmod +x <uh-groupings-ui-repo>/entrypoint.sh
   ```

2. **Update Dockerfile runtime stage** to match `services/ui/Dockerfile`:
   ```dockerfile
   # ...existing build stage...

   # Stage 2: Runtime Stage
   FROM eclipse-temurin:17-jre-alpine

   WORKDIR /app
   RUN apk add --no-cache logrotate
   COPY --from=builder /app/target/*.jar app.jar
   RUN mkdir -p /var/log/application/ui /logs/Archive && \
       chmod 755 /var/log/application/ui /logs/Archive
   COPY logrotate-ui.conf /etc/logrotate.d/ui
   COPY logback-spring.xml /app/logback-spring.xml
   COPY entrypoint.sh /app/entrypoint.sh
   RUN chmod +x /app/entrypoint.sh

   EXPOSE 3000
   HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
     CMD wget --quiet --tries=1 --spider http://localhost:3000/actuator/health || exit 1

   ENTRYPOINT ["/app/entrypoint.sh"]
   ```

3. **Update `application.properties`:**
   ```properties
   logging.config=classpath:logback-spring.xml
   logging.file.name=/var/log/application/ui/application.log
   logging.level.root=INFO
   logging.level.com.uh.groupings=DEBUG
   ```

4. **Test and commit** (same process as API).

**Deliverables:**
- [ ] UI container updated with log rotation
- [ ] Local Docker build and run successful
- [ ] Changes committed and pushed

---

### Phase 4: ECS Configuration Updates (Week 3)

#### 4.1 Update Task Definitions
**Goal:** Configure ECS tasks to mount EFS for persistent logs and use
CloudWatch for log streaming.

**Tools:** AWS CDK (recommended) or AWS Console

> **Prerequisite:** The EFS file system must be created first. This should be
> added to `DataStack` or `NetworkStack` (both are currently TODO placeholders).
> The EFS file system needs mount targets in each private subnet used by ECS
> tasks, and the security group must allow NFS (TCP port 2049) from the ECS
> task security group.

**Using AWS CDK (Recommended):**

Add to `infra/stacks/app_stack.py`:
```python
from aws_cdk import (
    aws_ecs as ecs,
    aws_efs as efs,
    aws_logs as logs,
)

# ...existing code...

# Reference EFS (created in DataStack or NetworkStack)
efs_file_system = efs.FileSystem.from_file_system_attributes(
    self, "LogsEfs",
    file_system_id="fs-XXXXXXXXX",          # Replace with actual ID
    security_group=efs_security_group,       # Must allow NFS from ECS SG
)

# Mount EFS volume in task definition
task_definition.add_volume(
    name="logs-volume",
    efs_volume_configuration=ecs.EfsVolumeConfiguration(
        file_system_id=efs_file_system.file_system_id,
        transit_encryption="ENABLED",
    ),
)

# Add mount points for API container
api_container.add_mount_points(
    ecs.MountPoint(
        source_volume="logs-volume",
        container_path="/var/log/application",
        read_only=False,
    ),
    ecs.MountPoint(
        source_volume="logs-volume",
        container_path="/logs",
        read_only=False,
    ),
)

# Configure CloudWatch logging
api_log_driver = ecs.LogDriver.aws_logs(
    log_group=logs.LogGroup.from_log_group_name(
        self, "api-logs", "/ecs/uh-groupings/api"
    ),
    stream_prefix="api-task",
)
```

**Using AWS Console:**

1. Go to ECS → Task Definitions → Create new revision
2. Under **Volumes**, add an EFS volume:
   - Name: `logs-volume`
   - Source: Select EFS file system
   - Enable transit encryption
3. Under each container, add **Mount points**:
   - Source volume: `logs-volume`
   - Container path: `/var/log/application` (read/write)
   - Container path: `/logs` (read/write)
4. Under **Log configuration**, set:
   - Log driver: `awslogs`
   - Log group: `/ecs/uh-groupings/api` (or `/ecs/uh-groupings/ui`)
   - Stream prefix: `api-task` (or `ui-task`)
5. Save new revision

**Deliverables:**
- [ ] Task definitions updated with EFS volume mounts
- [ ] CloudWatch logging configured for both containers
- [ ] New task definition revision created
- [ ] Task definition ARNs documented

**Success Criteria:**
- Task definition validates successfully
- EFS mount points reference correct file system
- CloudWatch log driver is configured
- New revision is available for deployment

---

#### 4.2 Deploy Updated Services
**Goal:** Update ECS services with new task definitions and container images

**Steps:**

1. **Update API service:**
   ```bash
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:LATEST \
     --force-new-deployment
   ```

2. **Update UI service:**
   ```bash
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-ui \
     --task-definition uh-groupings-ui:LATEST \
     --force-new-deployment
   ```

3. **Monitor rollout:**
   ```bash
   # Watch deployment progress (refresh every 10s)
   watch -n 10 'aws ecs describe-services \
     --cluster uh-groupings-cluster \
     --services uh-groupings-api uh-groupings-ui \
     --query "services[].{Name:serviceName,Running:runningCount,Pending:pendingCount,Deployments:deployments[].{Status:status,Running:runningCount,Desired:desiredCount}}"
   ```

4. **Verify logs are flowing:**
   ```bash
   # Check CloudWatch
   aws logs tail /ecs/uh-groupings/api --follow

   # Connect to a running container to check EFS
   aws ecs execute-command \
     --cluster uh-groupings-cluster \
     --task <TASK-ID> \
     --container uh-groupings-api \
     --interactive \
     --command "/bin/sh"

   # Inside container:
   ls -la /var/log/application/api/
   ls -la /logs/Archive/
   ```

**Deliverables:**
- [ ] Services updated with new task definitions
- [ ] Deployment completed successfully (PRIMARY deployment is steady-state)
- [ ] All tasks are in RUNNING state
- [ ] CloudWatch logs are flowing

**Success Criteria:**
- Services update without errors
- New tasks start successfully
- Logs appear in CloudWatch within 60 seconds
- No errors in application logs

---

### Phase 5: Monitoring & Alerts Setup (Week 3-4)

#### 5.1 Create CloudWatch Alarms
**Goal:** Set up monitoring for log rotation health and disk usage

**Using AWS CDK:**

Add to `app_stack.py` or a dedicated monitoring stack:
```python
from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
)

# SNS topic for alarm notifications
alarm_topic = sns.Topic(self, "log-alarm-topic",
    topic_name="uh-groupings-log-alarms",
)

# Alarm for high log volume
high_volume_alarm = cloudwatch.Alarm(self, "high-log-volume",
    metric=cloudwatch.Metric(
        namespace="AWS/Logs",
        metric_name="IncomingBytes",
        statistic="Sum",
        period=cdk.Duration.hours(1),
        dimensions_map={
            "LogGroupName": "/ecs/uh-groupings/api",
        },
    ),
    threshold=1073741824,  # 1GB per hour
    evaluation_periods=2,
    alarm_description="Alert when log volume exceeds 1GB/hour",
    alarm_name="uh-groupings-high-log-volume",
)

# Alarm for missing logs
no_logs_alarm = cloudwatch.Alarm(self, "no-logs",
    metric=cloudwatch.Metric(
        namespace="AWS/Logs",
        metric_name="IncomingLogEvents",
        statistic="Sum",
        period=cdk.Duration.minutes(30),
        dimensions_map={
            "LogGroupName": "/ecs/uh-groupings/api",
        },
    ),
    threshold=0,
    evaluation_periods=2,
    treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
    alarm_description="Alert when no logs received for 30 minutes",
    alarm_name="uh-groupings-no-logs",
)
```

**Deliverables:**
- [ ] High log volume alarm created
- [ ] Missing logs alarm created
- [ ] Alarms configured with proper thresholds
- [ ] SNS topic created for notifications

**Success Criteria:**
- Alarms appear in CloudWatch console
- Alarm thresholds are reasonable for your log volume
- Notifications can be tested

---

#### 5.2 Create CloudWatch Dashboard
**Goal:** Visualize log rotation and archival metrics

**Using AWS CDK:**

```python
dashboard = cloudwatch.Dashboard(self, "log-rotation-dashboard",
    dashboard_name="uh-groupings-log-rotation",
)

dashboard.add_widgets(
    cloudwatch.GraphWidget(
        title="Incoming Log Events (API)",
        left=[
            cloudwatch.Metric(
                namespace="AWS/Logs",
                metric_name="IncomingLogEvents",
                statistic="Sum",
                period=cdk.Duration.minutes(5),
                dimensions_map={"LogGroupName": "/ecs/uh-groupings/api"},
            ),
        ],
    ),
    cloudwatch.GraphWidget(
        title="Incoming Log Events (UI)",
        left=[
            cloudwatch.Metric(
                namespace="AWS/Logs",
                metric_name="IncomingLogEvents",
                statistic="Sum",
                period=cdk.Duration.minutes(5),
                dimensions_map={"LogGroupName": "/ecs/uh-groupings/ui"},
            ),
        ],
    ),
    cloudwatch.GraphWidget(
        title="Incoming Bytes (All Services)",
        left=[
            cloudwatch.Metric(
                namespace="AWS/Logs",
                metric_name="IncomingBytes",
                statistic="Sum",
                period=cdk.Duration.minutes(5),
                dimensions_map={"LogGroupName": "/ecs/uh-groupings/api"},
                label="API",
            ),
            cloudwatch.Metric(
                namespace="AWS/Logs",
                metric_name="IncomingBytes",
                statistic="Sum",
                period=cdk.Duration.minutes(5),
                dimensions_map={"LogGroupName": "/ecs/uh-groupings/ui"},
                label="UI",
            ),
        ],
    ),
)
```

**Deliverables:**
- [ ] CloudWatch dashboard created
- [ ] Key metrics visualized for both services
- [ ] Dashboard accessible from CloudWatch console

---

### Phase 6: Testing & Validation (Week 4)

#### 6.1 Functional Testing
**Goal:** Verify all three tiers are working correctly

**Test Cases:**

1. **Local Rotation (Tier 1):**
   ```bash
   # Connect to a running container
   aws ecs execute-command \
     --cluster uh-groupings-cluster \
     --task <TASK-ID> \
     --container uh-groupings-api \
     --interactive \
     --command "/bin/sh"

   # Inside container — force rotation and verify
   logrotate -d -f /etc/logrotate.d/api   # Dry run (check for errors)
   logrotate -f /etc/logrotate.d/api      # Actual rotation

   # Verify
   ls -la /var/log/application/api/
   ls -la /logs/Archive/
   ```

2. **CloudWatch Streaming (Tier 2):**
   ```bash
   # Tail recent logs
   aws logs tail /ecs/uh-groupings/api --follow

   # Run a CloudWatch Insights query
   QUERY_ID=$(aws logs start-query \
     --log-group-name /ecs/uh-groupings/api \
     --start-time $(python3 -c "import time; print(int(time.time()) - 3600)") \
     --end-time $(python3 -c "import time; print(int(time.time()))") \
     --query-string 'fields @timestamp, @message | sort @timestamp desc | limit 20' \
     --query 'queryId' --output text)

   # Wait a few seconds, then get results
   sleep 5
   aws logs get-query-results --query-id "$QUERY_ID"
   ```

   > **Note:** The `date -d` flag used in earlier versions of this document is
   > GNU-specific and does not work on macOS. The `python3 -c` approach above
   > is portable across Linux and macOS.

3. **S3 Export (Tier 3):**
   ```bash
   # Manually invoke the Lambda to test export
   FUNCTION_NAME=$(aws lambda list-functions \
     --query 'Functions[?contains(FunctionName, `export-logs`)].FunctionName' \
     --output text)

   aws lambda invoke \
     --function-name "$FUNCTION_NAME" \
     /tmp/export-response.json

   cat /tmp/export-response.json

   # Check export task status
   aws logs describe-export-tasks \
     --query 'exportTasks[?status.code==`COMPLETED`]'

   # Check S3 for exported logs
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   aws s3 ls "s3://uh-groupings-logs-archive-${ACCOUNT_ID}/cloudwatch-logs/" --recursive | head -20
   ```

**Checklist:**
- [ ] Logs are written to `/var/log/application/{service}/application.log`
- [ ] `logrotate -d -f` dry run reports no errors
- [ ] Rotation creates compressed files in `/logs/Archive/`
- [ ] `maxage 30` setting will delete files older than 30 days
- [ ] CloudWatch receives logs within 60 seconds of application output
- [ ] CloudWatch Insights queries return results
- [ ] Lambda export produces `COMPLETED` export tasks
- [ ] S3 bucket contains exported log files under `cloudwatch-logs/` prefix

---

#### 6.2 Performance Testing
**Goal:** Verify system handles expected log volumes

**Tests:**

1. **Log Volume Test:**
   - Generate expected daily log volume
   - Monitor disk usage, CPU, memory
   - Check rotation still completes on time

2. **Query Performance:**
   - Run CloudWatch Insights queries on large datasets
   - Verify response times are acceptable
   - Check for query failures

3. **Concurrent Access:**
   - Multiple services writing logs simultaneously
   - Verify no log loss or EFS contention
   - Monitor resource utilization

**Deliverables:**
- [ ] Performance test results documented
- [ ] No issues identified or documented as known limitations
- [ ] System performs within acceptable parameters

---

#### 6.3 Load Testing
**Goal:** Verify high-volume scenarios

**Test Scenarios:**
- 1GB/day log volume per service
- Peak hour traffic (5x normal volume)
- Sustained high volume for 24 hours

**Monitoring During Tests:**
- EFS utilization and throughput
- CloudWatch API throttling (check for `ThrottlingException`)
- S3 upload performance
- Lambda execution time and errors

**Deliverables:**
- [ ] Load test plan executed
- [ ] Performance metrics documented
- [ ] Scalability assessment complete

---

### Phase 7: Production Deployment (Week 4-5)

#### 7.1 Pre-Deployment Checklist
**Goal:** Ensure readiness for production deployment

```
Pre-Deployment Verification Checklist:

Infrastructure Setup:
  [ ] S3 bucket created with lifecycle policies
  [ ] S3 bucket policy allows CloudWatch Logs export (Phase 2.2)
  [ ] CloudWatch log groups created with 7-day retention
  [ ] Lambda function deployed and manually tested
  [ ] EventBridge rule scheduled for 2 AM UTC
  [ ] IAM roles and policies configured

Container Updates:
  [ ] API service image built and pushed to ECR
  [ ] UI service image built and pushed to ECR
  [ ] Images tested in staging/test environment
  [ ] Images tagged with version

ECS Configuration:
  [ ] EFS file system created with mount targets
  [ ] Task definitions updated with EFS mounts
  [ ] CloudWatch logging configured in task definitions
  [ ] Task definitions validated in staging

Monitoring:
  [ ] CloudWatch alarms created and tested
  [ ] Dashboard created and accessible
  [ ] SNS topics configured for notifications
  [ ] On-call rotation informed of deployment

Documentation:
  [ ] Runbooks updated with new monitoring procedures
  [ ] Team trained on CloudWatch dashboard
  [ ] Escalation procedures documented
  [ ] Rollback procedures documented and tested

Approvals:
  [ ] Security team approval obtained
  [ ] Infrastructure team approval obtained
  [ ] Application team approval obtained
  [ ] Change management ticket approved
```

---

#### 7.2 Production Deployment Steps
**Goal:** Deploy to production with minimal downtime

**Timeline:** Plan for 2-hour maintenance window

1. **Backup current state (T+0:00)**
   ```bash
   # Create EFS backup via AWS Backup
   aws backup start-backup-job \
     --backup-vault-name Default \
     --resource-arn arn:aws:elasticfilesystem:<REGION>:<ACCOUNT>:file-system/fs-XXXXXXXX \
     --iam-role-arn arn:aws:iam::<ACCOUNT>:role/aws-service-role/backup.amazonaws.com/AWSBackupDefaultServiceRole
   ```

   > **Note:** There is no `aws efs create-backup` command. EFS backups are
   > managed through the AWS Backup service.

2. **Update Services (T+0:10)**
   ```bash
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:LATEST \
     --force-new-deployment

   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-ui \
     --task-definition uh-groupings-ui:LATEST \
     --force-new-deployment
   ```

3. **Monitor Rollout (T+0:10 to T+1:00)**
   ```bash
   # Watch deployment progress (refresh every 10s)
   watch -n 10 'aws ecs describe-services \
     --cluster uh-groupings-cluster \
     --services uh-groupings-api uh-groupings-ui \
     --query "services[].{Name:serviceName,Running:runningCount,Pending:pendingCount,Deployments:deployments[].{Status:status,Running:runningCount,Desired:desiredCount}}"
   ```

4. **Verify logs are flowing (T+1:00)**
   ```bash
   # Check logs in CloudWatch
   aws logs tail /ecs/uh-groupings/api --since 5m
   aws logs tail /ecs/uh-groupings/ui --since 5m

   # Check for errors in the last 10 minutes
   QUERY_ID=$(aws logs start-query \
     --log-group-name /ecs/uh-groupings/api \
     --start-time $(python3 -c "import time; print(int(time.time()) - 600)") \
     --end-time $(python3 -c "import time; print(int(time.time()))") \
     --query-string 'fields @message | filter @message like /ERROR/' \
     --query 'queryId' --output text)
   sleep 5
   aws logs get-query-results --query-id "$QUERY_ID"
   ```

5. **Test Rotation (T+1:00 to T+1:30)**
   ```bash
   # Connect to a running container
   aws ecs execute-command \
     --cluster uh-groupings-cluster \
     --task <TASK-ID> \
     --container uh-groupings-api \
     --interactive \
     --command "/bin/sh"

   # Inside container:
   logrotate -d -f /etc/logrotate.d/api   # Dry run
   logrotate -f /etc/logrotate.d/api      # Actual rotation
   ls -la /logs/Archive/
   ```

6. **Final Validation (T+1:30 to T+2:00)**
   - [ ] Application health checks passing
   - [ ] CloudWatch logs flowing for both services
   - [ ] No ERROR-level logs in last 30 minutes
   - [ ] S3 bucket accessible
   - [ ] CloudWatch dashboard showing metrics

---

#### 7.3 Post-Deployment Verification (Days 1-7)
**Goal:** Verify system is stable in production

**Daily Checks:**
- [ ] **Day 1:** All logs flowing, no errors, health checks passing
- [ ] **Day 2:** First logrotate execution occurred (check `/logs/Archive/`)
- [ ] **Day 3:** CloudWatch Insights queries working with real data
- [ ] **Day 7:** First automated S3 export completed (Lambda runs at 2 AM UTC daily)

**Week 1 Review:**
- [ ] Log volume metrics reviewed against projections
- [ ] Cost analysis conducted (CloudWatch ingestion, EFS storage)
- [ ] Alarms reviewed for false positives
- [ ] Documentation updated with actual metrics and observations

---

### Phase 8: Operational Handoff (Week 5)

#### 8.1 Team Training
**Goal:** Ensure operations team can manage the system

**Training Topics:**
- How the three-tier system works
- Monitoring via CloudWatch dashboard
- Responding to alarms
- Querying logs via CloudWatch Insights
- Checking S3 archive and retrieving Glacier objects
- Troubleshooting common issues (see `LOG_ROTATION.md`)

**Training Materials:**
- [ ] Runbook created
- [ ] Video walkthrough recorded
- [ ] Quick reference guide printed
- [ ] Escalation procedures documented

---

#### 8.2 Documentation Handoff
**Goal:** Complete all documentation

**Deliverables:**
- [ ] Implementation guide (this document)
- [ ] Operational runbook
- [ ] Troubleshooting guide (see `LOG_ROTATION.md`)
- [ ] Cost tracking spreadsheet
- [ ] Architecture diagram (see `DIAGRAMS.md`)
- [ ] Contact list for escalation

---

### Phase 9: Optimization (Ongoing)

#### 9.1 Cost Optimization
**Goal:** Reduce operational costs over time

**Quarterly Reviews:**
- Analyze actual log volumes vs. projections
- Review S3 storage costs across tiers (Standard, Glacier, Deep Archive)
- Adjust retention policies if needed
- Consider log sampling or filtering for high-volume, low-value logs

---

#### 9.2 Monitoring Optimization
**Goal:** Refine alarms based on real-world behavior

**Monthly Reviews:**
- Analyze alarm firing patterns
- Adjust thresholds based on observed baseline
- Remove false positive alarms
- Add new alarms for emerging issues

---

## Implementation Roles & Responsibilities

| Role | Responsibilities |
|------|------------------|
| **Project Lead** | Overall coordination, approvals, timeline management |
| **DevOps Engineer** | Infrastructure setup, CDK deployment, task definition updates |
| **Application Developer** | Container updates, logback configuration, service testing |
| **Security Engineer** | IAM policy review, encryption verification, compliance check |
| **Operations Team** | Runbook creation, team training, post-deployment monitoring |

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-----------|--------|-----------|
| **High EFS costs** | Medium | High | Monitor usage, enforce `maxage 30` in logrotate |
| **CloudWatch API throttling** | Low | Medium | Lambda uses single `CreateExportTask` per group (within limits) |
| **Log loss during migration** | Low | High | Test in staging first; old containers continue logging until replaced |
| **Application startup delay** | Medium | Low | `entrypoint.sh` runs logrotate in background, does not block app start |
| **Disk space exhaustion** | Low | High | Logrotate `maxage 30` + `rotate 7` enforces limits; monitor EFS metrics |
| **S3 export fails silently** | Medium | Medium | Add CloudWatch alarm on Lambda errors; verify exports weekly |
| **Missing S3 bucket policy** | High | High | Phase 2.2 explicitly addresses this; test export before production |

---

## Success Criteria

### Functional Requirements
- [ ] Logs rotate daily and are compressed
- [ ] Rotated logs are archived to `/logs/Archive`
- [ ] Logs are streamed to CloudWatch in real-time
- [ ] Logs are exported to S3 daily
- [ ] S3 lifecycle policies transition old logs to Glacier/Deep Archive
- [ ] Compliance retention window (7 years) is met

### Non-Functional Requirements
- [ ] Zero application code changes required (only Dockerfile and config)
- [ ] Minimal performance impact (<5% CPU/memory overhead)
- [ ] Log queries complete in <30 seconds
- [ ] 99.9% log delivery success rate
- [ ] Cost <$10/month per service pair

### Operational Requirements
- [ ] Operations team can monitor system via CloudWatch dashboard
- [ ] Alarms alert on critical issues within 5 minutes
- [ ] Runbook enables fast incident response
- [ ] Team trained on new monitoring procedures

---

## Rollback Plan

If critical issues arise, the system can be rolled back:

1. **Revert ECS services to previous task definition:**
   ```bash
   # List task definition revisions
   aws ecs list-task-definitions \
     --family-prefix uh-groupings-api \
     --sort DESC --max-items 5

   # Update service to previous revision
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:<PREVIOUS_REVISION> \
     --force-new-deployment
   ```

2. **Revert CloudWatch logging** — only needed if log groups are causing issues;
   the log groups themselves are harmless and can be retained.

3. **Restore EFS from backup** (if data corruption):
   ```bash
   aws backup start-restore-job \
     --recovery-point-arn <RECOVERY_POINT_ARN> \
     --iam-role-arn <BACKUP_ROLE_ARN> \
     --metadata '{"file-system-id":"fs-XXXXXXXX","newFileSystem":"false"}'
   ```

4. **Keep S3 bucket** — log archives are append-only and should not be deleted
   even during rollback. They serve as the audit trail.

**Rollback Duration:** ~30 minutes (ECS rolling update)

---

## Next Steps

1. [ ] Obtain stakeholder approval for this plan
2. [ ] Schedule kickoff meeting
3. [ ] Assign team members to phases
4. [ ] Complete prerequisite CDK stacks (`network_stack.py`, `data_stack.py`, `app_stack.py`)
5. [ ] Begin Phase 1: Planning & Preparation
6. [ ] Track progress against timeline
7. [ ] Conduct post-implementation review

---

## Related Documentation

- **Log Rotation Configuration:** `LOG_ROTATION.md` — detailed configuration options, tuning, and troubleshooting
- **Architecture Diagrams:** `DIAGRAMS.md` — visual architecture, flows, and cost breakdown
- **AWS Architecture:** `ARCHITECTURE.md` — VPC, ECS, RDS, and overall infrastructure
- **Project Structure:** `STRUCTURE.md` — repository layout and file organization

---

**Document Owner:** DevOps Team
**Last Updated:** March 25, 2026
**Version:** 1.1.0
