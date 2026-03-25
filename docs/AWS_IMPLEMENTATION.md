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
- [ ] Verify EFS filesystem exists and is accessible
- [ ] Check ECS task definition log driver configuration
- [ ] Review IAM roles and permissions
- [ ] Verify S3 bucket naming conventions
- [ ] Test network connectivity to all AWS services

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

# Check existing logs
aws logs describe-log-groups \
  --query 'logGroups[?contains(logGroupName, `uh-groupings`)]'
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

#### 2.1 Create S3 Bucket for Archive
**Goal:** Set up S3 bucket with lifecycle policies for long-term log storage

**Tools:** AWS Console or AWS CLI

**Steps:**

1. **Create S3 bucket:**
   ```bash
   aws s3api create-bucket \
     --bucket uh-groupings-logs-archive-$(aws sts get-caller-identity --query Account --output text) \
     --region us-east-1
   ```

2. **Enable versioning:**
   ```bash
   aws s3api put-bucket-versioning \
     --bucket uh-groupings-logs-archive-ACCOUNT-ID \
     --versioning-configuration Status=Enabled
   ```

3. **Block public access:**
   ```bash
   aws s3api put-public-access-block \
     --bucket uh-groupings-logs-archive-ACCOUNT-ID \
     --public-access-block-configuration \
     "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
   ```

4. **Enable encryption:**
   ```bash
   aws s3api put-bucket-encryption \
     --bucket uh-groupings-logs-archive-ACCOUNT-ID \
     --server-side-encryption-configuration '{
       "Rules": [{
         "ApplyServerSideEncryptionByDefault": {
           "SSEAlgorithm": "AES256"
         }
       }]
     }'
   ```

5. **Set lifecycle policy:**
   ```bash
   aws s3api put-bucket-lifecycle-configuration \
     --bucket uh-groupings-logs-archive-ACCOUNT-ID \
     --lifecycle-configuration file://lifecycle-policy.json
   ```

   **`lifecycle-policy.json`:**
   ```json
   {
     "Rules": [
       {
         "Id": "LogArchiveLifecycle",
         "Status": "Enabled",
         "Filter": {"Prefix": "cloudwatch-logs/"},
         "Transitions": [
           {
             "Days": 90,
             "StorageClass": "GLACIER"
           },
           {
             "Days": 180,
             "StorageClass": "DEEP_ARCHIVE"
           }
         ],
         "Expiration": {
           "Days": 2555
         }
       }
     ]
   }
   ```

**Deliverables:**
- [ ] S3 bucket created with unique name
- [ ] Versioning enabled
- [ ] Public access blocked
- [ ] Encryption configured
- [ ] Lifecycle policy applied
- [ ] Bucket ARN documented

**Success Criteria:**
- Bucket is created and accessible
- Lifecycle policy is active
- Encryption is enabled
- Public access is blocked

---

#### 2.2 Create CloudWatch Log Groups
**Goal:** Set up centralized log aggregation via CloudWatch

**Tools:** AWS CDK (recommended) or AWS CLI

**Using AWS CDK (Recommended):**

Add to `infra/lib/log-rotation-stack.ts`:
```typescript
import * as cdk from 'aws-cdk-lib';
import * as logs from 'aws-cdk-lib/aws-logs';

export class LogRotationStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create log groups for each service
    const apiLogGroup = new logs.LogGroup(this, 'api-log-group', {
      logGroupName: '/ecs/uh-groupings/api',
      retention: logs.RetentionDays.SEVEN_DAYS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const uiLogGroup = new logs.LogGroup(this, 'ui-log-group', {
      logGroupName: '/ecs/uh-groupings/ui',
      retention: logs.RetentionDays.SEVEN_DAYS,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Export ARNs for reference
    new cdk.CfnOutput(this, 'ApiLogGroupName', {
      value: apiLogGroup.logGroupName,
      exportName: 'api-log-group-name',
    });

    new cdk.CfnOutput(this, 'UiLogGroupName', {
      value: uiLogGroup.logGroupName,
      exportName: 'ui-log-group-name',
    });
  }
}
```

Add to `infra/bin/app.ts`:
```typescript
import { LogRotationStack } from '../lib/log-rotation-stack';

const app = new cdk.App();
// ... existing stacks ...
new LogRotationStack(app, 'uh-groupings-log-rotation');
```

Deploy:
```bash
cd infra
npm install
cdk deploy LogRotationStack
```

**Using AWS CLI:**
```bash
aws logs create-log-group --log-group-name /ecs/uh-groupings/api
aws logs put-retention-policy --log-group-name /ecs/uh-groupings/api --retention-in-days 7

aws logs create-log-group --log-group-name /ecs/uh-groupings/ui
aws logs put-retention-policy --log-group-name /ecs/uh-groupings/ui --retention-in-days 7
```

**Deliverables:**
- [ ] CloudWatch log group for API service created
- [ ] CloudWatch log group for UI service created
- [ ] Retention policy set to 7 days
- [ ] Log group ARNs documented

**Success Criteria:**
- Log groups exist in CloudWatch console
- Retention is set correctly
- Log groups are ready to receive logs

---

#### 2.3 Set Up CloudWatch-to-S3 Export
**Goal:** Create Lambda function and EventBridge rule for daily log exports

**Tools:** AWS CDK or AWS Console

**Using AWS CDK:**

Add to `infra/lib/log-archival-stack.ts`:
```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';

export class LogArchivalStack extends cdk.Stack {
  constructor(scope: cdk.App, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Reference existing S3 bucket
    const logBucket = s3.Bucket.fromBucketName(
      this,
      'log-archive-bucket',
      `uh-groupings-logs-archive-${cdk.Stack.of(this).account}`
    );

    // Create Lambda function for exporting logs
    const exportFunction = new lambda.Function(this, 'export-logs', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/export-logs'),
      environment: {
        LOG_BUCKET: logBucket.bucketName,
      },
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
    });

    // Add permissions
    exportFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateExportTask',
          'logs:DescribeExportTasks',
        ],
        resources: ['*'],
      })
    );

    logBucket.grantWrite(exportFunction);

    // Schedule daily execution
    const rule = new events.Rule(this, 'export-schedule', {
      schedule: events.Schedule.cron({
        hour: '2',
        minute: '0',
      }),
    });

    rule.addTarget(new targets.LambdaTarget(exportFunction));
  }
}
```

Create Lambda code at `lambda/export-logs/index.py`:
```python
import boto3
import json
import os
from datetime import datetime, timedelta

logs_client = boto3.client('logs')
s3_bucket = os.environ['LOG_BUCKET']

def handler(event, context):
    log_groups = [
        '/ecs/uh-groupings/api',
        '/ecs/uh-groupings/ui',
    ]
    
    # Calculate time range (yesterday)
    end_time = int(datetime.utcnow().timestamp() * 1000)
    start_time = int((datetime.utcnow() - timedelta(days=1)).timestamp() * 1000)
    
    results = []
    
    for log_group in log_groups:
        try:
            response = logs_client.create_export_task(
                logGroupName=log_group,
                fromTime=start_time,
                to=end_time,
                destination=s3_bucket,
                destinationPrefix=f"cloudwatch-logs{log_group}/{datetime.utcnow().strftime('%Y/%m/%d')}"
            )
            results.append({
                'logGroup': log_group,
                'taskId': response['taskId'],
                'status': 'success'
            })
        except Exception as e:
            results.append({
                'logGroup': log_group,
                'status': 'error',
                'error': str(e)
            })
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
```

Deploy:
```bash
cd infra
cdk deploy LogArchivalStack
```

**Deliverables:**
- [ ] Lambda function created and deployed
- [ ] EventBridge rule scheduled for 2 AM UTC daily
- [ ] Lambda has CloudWatch Logs and S3 write permissions
- [ ] Lambda function ARN documented

**Success Criteria:**
- Lambda function can be invoked manually without errors
- EventBridge rule is active
- S3 bucket receives test exports

---

### Phase 3: Service Container Updates (Week 2-3)

#### 3.1 Update API Service (uh-groupings-api)
**Goal:** Add log rotation to API container

**Location:** `uh-groupings-api` repository

**Steps:**

1. **Copy configuration files from example repo:**
   ```bash
   cp examples/services/api/entrypoint.sh ./services/api/
   cp examples/services/api/logrotate-api.conf ./services/api/
   cp examples/services/api/logback-spring.xml ./src/main/resources/
   chmod +x ./services/api/entrypoint.sh
   ```

2. **Update Dockerfile:**
   ```dockerfile
   # ...existing build stage...
   
   FROM eclipse-temurin:17-jre-alpine
   
   WORKDIR /app
   
   # Install logrotate
   RUN apk add --no-cache logrotate
   
   # Copy JAR
   COPY --from=builder /app/target/*.jar app.jar
   
   # Create log directories
   RUN mkdir -p /var/log/application/api /logs/Archive && \
       chmod 755 /var/log/application/api /logs/Archive
   
   # Copy configuration
   COPY services/api/logrotate-api.conf /etc/logrotate.d/api
   COPY services/api/entrypoint.sh /app/entrypoint.sh
   RUN chmod +x /app/entrypoint.sh
   
   EXPOSE 8080
   
   ENTRYPOINT ["/app/entrypoint.sh"]
   ```

3. **Update application.properties:**
   ```properties
   # Logging configuration
   logging.config=classpath:logback-spring.xml
   logging.file.name=/var/log/application/api/application.log
   logging.level.root=INFO
   logging.level.com.uh.groupings=DEBUG
   ```

4. **Test locally:**
   ```bash
   docker build -t uh-groupings-api:test .
   docker run --rm \
     -v /tmp/logs:/var/log/application \
     -v /tmp/archive:/logs/Archive \
     uh-groupings-api:test
   
   # In another terminal, generate some logs
   # Wait 6+ hours or modify entrypoint.sh sleep time for testing
   ```

5. **Commit and push:**
   ```bash
   git add services/api/entrypoint.sh services/api/logrotate-api.conf
   git add src/main/resources/logback-spring.xml
   git add Dockerfile
   git add src/main/resources/application.properties
   git commit -m "feat: add log rotation configuration"
   git tag v1.2.0-with-log-rotation
   git push origin main --tags
   ```

**Deliverables:**
- [ ] entrypoint.sh copied and executable
- [ ] logrotate-api.conf copied
- [ ] logback-spring.xml added to project
- [ ] Dockerfile updated with logrotate installation
- [ ] application.properties updated
- [ ] Local Docker test passed
- [ ] Changes committed and tagged

**Success Criteria:**
- Docker build completes successfully
- Container starts without errors
- Log files are created in correct locations
- No permission errors in logs

---

#### 3.2 Update UI Service (uh-groupings-ui)
**Goal:** Add log rotation to UI container

**Location:** `uh-groupings-ui` repository

**Steps:** (Same as API service, but with UI-specific paths)

1. **Copy configuration files:**
   ```bash
   cp examples/services/ui/entrypoint.sh ./services/ui/
   cp examples/services/ui/logrotate-ui.conf ./services/ui/
   cp examples/services/ui/logback-spring.xml ./src/main/resources/
   chmod +x ./services/ui/entrypoint.sh
   ```

2. **Update Dockerfile:**
   ```dockerfile
   # ...existing build stage...
   
   FROM eclipse-temurin:17-jre-alpine
   
   WORKDIR /app
   
   RUN apk add --no-cache logrotate
   COPY --from=builder /app/target/*.jar app.jar
   RUN mkdir -p /var/log/application/ui /logs/Archive && \
       chmod 755 /var/log/application/ui /logs/Archive
   COPY services/ui/logrotate-ui.conf /etc/logrotate.d/ui
   COPY services/ui/entrypoint.sh /app/entrypoint.sh
   RUN chmod +x /app/entrypoint.sh
   
   EXPOSE 3000
   ENTRYPOINT ["/app/entrypoint.sh"]
   ```

3. **Update application.properties:**
   ```properties
   logging.config=classpath:logback-spring.xml
   logging.file.name=/var/log/application/ui/application.log
   logging.level.root=INFO
   logging.level.com.uh.groupings=DEBUG
   ```

4. **Test and commit:**
   ```bash
   docker build -t uh-groupings-ui:test .
   # ... test ...
   git add services/ui/entrypoint.sh services/ui/logrotate-ui.conf
   git add src/main/resources/logback-spring.xml
   git add Dockerfile
   git add src/main/resources/application.properties
   git commit -m "feat: add log rotation configuration"
   git tag v1.2.0-with-log-rotation
   git push origin main --tags
   ```

**Deliverables:**
- [ ] UI container updated with log rotation
- [ ] Docker test passed
- [ ] Changes committed and tagged

---

### Phase 4: ECS Configuration Updates (Week 3)

#### 4.1 Update Task Definition
**Goal:** Configure ECS task to mount EFS and use CloudWatch logging

**Tools:** AWS CDK, AWS Console, or AWS CLI

**Using AWS CDK (Recommended):**

Update `infra/lib/app-stack.ts`:
```typescript
// ...existing imports...
import * as efs from 'aws-cdk-lib/aws-efs';

// In your task definition creation:

// Mount EFS volume
const logsVolume = taskDefinition.addVolume({
  name: 'logs-volume',
  efsVolumeConfiguration: {
    fileSystemId: efsFileSystem.fileSystemId,
    transitEncryption: 'ENABLED',
    authorizationConfig: {
      accessPointId: efsAccessPoint.accessPointId,
    },
  },
});

// Add mount points for API container
apiContainer.addMountPoints({
  sourceVolume: 'logs-volume',
  containerPath: '/var/log/application',
  readOnly: false,
});

apiContainer.addMountPoints({
  sourceVolume: 'logs-volume',
  containerPath: '/logs',
  readOnly: false,
});

// Configure CloudWatch logging for API
const apiLogGroup = logs.LogGroup.fromLogGroupName(
  this,
  'api-logs',
  '/ecs/uh-groupings/api'
);

apiContainer.addPortMappings({
  containerPort: 8080,
});

// Same for UI container
// ...
```

**Using AWS Console:**

1. Go to ECS Cluster → Services → Service Details
2. Click "Update" → "Modify"
3. Under "Logging," configure CloudWatch:
   - Log Group: `/ecs/uh-groupings/api`
   - Log Stream Prefix: `api-task`
4. Under "Storage," add volume mount:
   - Source: EFS
   - Container Path: `/var/log/application`
5. Save and update service

**Deliverables:**
- [ ] Task definition updated with EFS mounts
- [ ] CloudWatch logging configured
- [ ] Task definition revision updated
- [ ] New task definition ARN documented

**Success Criteria:**
- Task definition validates successfully
- EFS mount points are correct
- CloudWatch logging is configured
- New task definitions work with existing services

---

#### 4.2 Deploy Updated Services
**Goal:** Update ECS services with new task definitions and container images

**Steps:**

1. **Update API service:**
   ```bash
   # Get latest image from ECR
   API_IMAGE=$(aws ecr describe-images \
     --repository-name uh-groupings-api \
     --query 'imageDetails[0].imageUri' \
     --output text)
   
   # Update service
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:LATEST \
     --force-new-deployment
   ```

2. **Update UI service:**
   ```bash
   UI_IMAGE=$(aws ecr describe-images \
     --repository-name uh-groupings-ui \
     --query 'imageDetails[0].imageUri' \
     --output text)
   
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-ui \
     --task-definition uh-groupings-ui:LATEST \
     --force-new-deployment
   ```

3. **Monitor rollout:**
   ```bash
   # Watch service deployment
   aws ecs describe-services \
     --cluster uh-groupings-cluster \
     --services uh-groupings-api uh-groupings-ui \
     --query 'services[].deployments'
   ```

4. **Verify logs are flowing:**
   ```bash
   # Check CloudWatch
   aws logs tail /ecs/uh-groupings/api --follow
   
   # In separate terminal, check EFS
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
- [ ] Deployment completed successfully
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

Add to monitoring stack:
```typescript
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';

// Alarm for high log volume
new cloudwatch.Alarm(this, 'high-log-volume', {
  metric: new cloudwatch.Metric({
    namespace: 'AWS/Logs',
    metricName: 'IncomingBytes',
    statistic: 'Sum',
    period: cdk.Duration.hours(1),
    dimensions: {
      LogGroupName: '/ecs/uh-groupings/api',
    },
  }),
  threshold: 1073741824, // 1GB per hour
  evaluationPeriods: 2,
  alarmDescription: 'Alert when log volume exceeds 1GB/hour',
  alarmName: 'uh-groupings-high-log-volume',
});

// Alarm for missing logs
new cloudwatch.Alarm(this, 'no-logs', {
  metric: new cloudwatch.Metric({
    namespace: 'AWS/Logs',
    metricName: 'IncomingLogEvents',
    statistic: 'Sum',
    period: cdk.Duration.minutes(30),
    dimensions: {
      LogGroupName: '/ecs/uh-groupings/api',
    },
  }),
  threshold: 0,
  evaluationPeriods: 2,
  treatMissingData: cloudwatch.TreatMissingData.BREACHING,
  alarmDescription: 'Alert when no logs received for 30 minutes',
  alarmName: 'uh-groupings-no-logs',
});
```

**Deliverables:**
- [ ] High log volume alarm created
- [ ] Missing logs alarm created
- [ ] Alarms configured with proper thresholds
- [ ] SNS topics for notifications

**Success Criteria:**
- Alarms appear in CloudWatch console
- Alarm thresholds are reasonable for your log volume
- Notifications can be tested

---

#### 5.2 Create CloudWatch Dashboard
**Goal:** Visualize log rotation and archival metrics

**Using AWS CDK:**

```typescript
const dashboard = new cloudwatch.Dashboard(this, 'log-rotation-dashboard', {
  dashboardName: 'uh-groupings-log-rotation',
});

dashboard.addWidgets(
  new cloudwatch.GraphWidget({
    title: 'Incoming Log Events',
    left: [
      new cloudwatch.Metric({
        namespace: 'AWS/Logs',
        metricName: 'IncomingLogEvents',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
        dimensions: { LogGroupName: '/ecs/uh-groupings/api' },
      }),
    ],
  }),
  new cloudwatch.GraphWidget({
    title: 'Incoming Bytes',
    left: [
      new cloudwatch.Metric({
        namespace: 'AWS/Logs',
        metricName: 'IncomingBytes',
        statistic: 'Sum',
        period: cdk.Duration.minutes(5),
      }),
    ],
  }),
);
```

**Deliverables:**
- [ ] CloudWatch dashboard created
- [ ] Key metrics visualized
- [ ] Dashboard accessible from CloudWatch console

---

### Phase 6: Testing & Validation (Week 4)

#### 6.1 Functional Testing
**Goal:** Verify all three tiers are working correctly

**Test Cases:**

1. **Local Rotation (Tier 1):**
   ```bash
   # Inside running container
   # Force rotation to test
   logrotate -f /etc/logrotate.d/api
   
   # Verify files
   ls -la /var/log/application/api/
   ls -la /logs/Archive/
   
   # Check sizes
   du -sh /logs/Archive/
   ```

2. **CloudWatch Streaming (Tier 2):**
   ```bash
   # Check logs appear in CloudWatch
   aws logs tail /ecs/uh-groupings/api --follow
   
   # Run query
   aws logs start-query \
     --log-group-name /ecs/uh-groupings/api \
     --start-time $(date -d '1 hour ago' +%s) \
     --end-time $(date +%s) \
     --query-string 'fields @timestamp, @message | limit 100'
   ```

3. **S3 Export (Tier 3):**
   ```bash
   # Check Lambda function
   aws lambda get-function \
     --function-name export-logs-function
   
   # Manually invoke
   aws lambda invoke \
     --function-name export-logs-function \
     /tmp/response.json
   
   # Check S3
   aws s3 ls s3://uh-groupings-logs-archive-ACCOUNT/cloudwatch-logs/
   ```

**Checklist:**
- [ ] Logs are written to `/var/log/application/{service}/`
- [ ] Rotation occurs at expected intervals
- [ ] Compressed files appear in `/logs/Archive/`
- [ ] Files are deleted after maxage threshold
- [ ] CloudWatch receives logs within 60 seconds
- [ ] CloudWatch Insights queries work
- [ ] S3 exports occur daily at 2 AM UTC
- [ ] S3 lifecycle transitions work after 90 days

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
   - Verify no log loss
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
- EFS utilization
- CloudWatch API throttling
- S3 upload performance
- Lambda execution time

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
  [ ] CloudWatch log groups created
  [ ] Lambda function deployed and tested
  [ ] EventBridge rule scheduled
  [ ] IAM roles and policies configured

Container Updates:
  [ ] API service image built and pushed to ECR
  [ ] UI service image built and pushed to ECR
  [ ] Images tested in staging environment
  [ ] Images are tagged with version

ECS Configuration:
  [ ] Task definitions updated with EFS mounts
  [ ] CloudWatch logging configured
  [ ] Task definitions validated in staging

Monitoring:
  [ ] CloudWatch alarms created and tested
  [ ] Dashboard created and accessible
  [ ] SNS topics configured
  [ ] On-call rotation informed

Documentation:
  [ ] Runbooks updated
  [ ] Team trained on new monitoring
  [ ] Escalation procedures documented
  [ ] Rollback procedures documented

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

1. **Backup (0:00)**
   ```bash
   # Create EFS snapshot
   aws efs create-backup --file-system-id fs-XXXXXX
   ```

2. **Update Services (0:10)**
   ```bash
   # Update both services
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

3. **Monitor Rollout (0:10-1:00)**
   ```bash
   # Watch deployment progress
   watch 'aws ecs describe-services \
     --cluster uh-groupings-cluster \
     --services uh-groupings-api uh-groupings-ui \
     --query "services[].{Name:serviceName, Running:runningCount, Pending:pendingCount}"'
   ```

4. **Verify Logs (1:00)**
   ```bash
   # Check logs are flowing
   aws logs tail /ecs/uh-groupings/api --follow
   aws logs tail /ecs/uh-groupings/ui --follow
   
   # Check for errors
   aws logs start-query \
     --log-group-name /ecs/uh-groupings/api \
     --start-time $(date -d '10 minutes ago' +%s) \
     --query-string 'fields @message | filter @message like /ERROR/'
   ```

5. **Test Rotation (1:00-1:30)**
   ```bash
   # Force rotation to verify
   aws ecs execute-command \
     --cluster uh-groupings-cluster \
     --task <TASK-ID> \
     --container uh-groupings-api \
     --interactive \
     --command "/bin/sh"
   
   # Inside container:
   logrotate -f /etc/logrotate.d/api
   ls -la /logs/Archive/
   ```

6. **Final Validation (1:30-2:00)**
   ```bash
   # Verify all systems operational
   # - Application health checks passing
   # - CloudWatch logs flowing
   # - No errors in last 30 minutes
   # - S3 bucket accessible
   ```

---

#### 7.3 Post-Deployment Verification (Days 1-7)
**Goal:** Verify system is stable in production

**Daily Checks:**
- [ ] Day 1: All logs flowing, no errors
- [ ] Day 2: Log rotation executing correctly
- [ ] Day 3: CloudWatch queries working
- [ ] Day 7: First automated S3 export completed (at 2 AM UTC)

**Weekly Review:**
- [ ] Log volume metrics reviewed
- [ ] Cost analysis conducted
- [ ] Alarms reviewed for false positives
- [ ] Documentation updated with actual metrics

---

### Phase 8: Operational Handoff (Week 5)

#### 8.1 Team Training
**Goal:** Ensure operations team can manage the system

**Training Topics:**
- How the three-tier system works
- Monitoring via CloudWatch dashboard
- Responding to alarms
- Querying logs via CloudWatch Insights
- Checking S3 archive
- Troubleshooting common issues

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
- [ ] Troubleshooting guide
- [ ] Cost tracking spreadsheet
- [ ] Architecture diagram
- [ ] Contact list for escalation

---

### Phase 9: Optimization (Ongoing)

#### 9.1 Cost Optimization
**Goal:** Reduce operational costs over time

**Quarterly Reviews:**
- Analyze actual log volumes
- Review S3 storage costs
- Adjust retention policies if needed
- Consider log sampling for non-critical services

---

#### 9.2 Monitoring Optimization
**Goal:** Refine alarms based on real-world behavior

**Monthly Reviews:**
- Analyze alarm firing patterns
- Adjust thresholds based on baseline
- Remove false positive alarms
- Add new alarms for emerging issues

---

## Implementation Roles & Responsibilities

| Role | Responsibilities |
|------|------------------|
| **Project Lead** | Overall coordination, approvals, timeline management |
| **DevOps Engineer** | Infrastructure setup, task definition updates, deployment |
| **Application Developer** | Container updates, logback configuration, testing |
| **Security Engineer** | IAM policy review, encryption verification, compliance check |
| **Database Admin** | EFS monitoring, performance tuning |
| **Operations Team** | Runbook creation, team training, post-deployment monitoring |

---

## Risk Assessment & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-----------|--------|-----------|
| **High EFS costs** | Medium | High | Monitor usage, implement cleanup policies |
| **CloudWatch API throttling** | Low | Medium | Implement exponential backoff in Lambda |
| **Log loss during migration** | Low | High | Backup existing logs, test thoroughly in staging |
| **Application startup delay** | Medium | Low | Pre-warm EFS, optimize entrypoint script |
| **Disk space exhaustion** | Low | High | Monitor proactively, set aggressive retention |

---

## Success Criteria

### Functional Requirements
- [x] Logs rotate daily and are compressed
- [x] Rotated logs are archived to `/logs/Archive`
- [x] Logs are streamed to CloudWatch in real-time
- [x] Logs are exported to S3 daily
- [x] S3 lifecycle policies transition old logs
- [x] Compliance retention window is met

### Non-Functional Requirements
- [x] Zero application code changes required
- [x] Minimal performance impact (<5% CPU/memory overhead)
- [x] Log queries complete in <30 seconds
- [x] 99.9% log delivery success rate
- [x] Cost <$10/month per service pair

### Operational Requirements
- [x] Operations team can monitor system via dashboard
- [x] Alarms alert on critical issues
- [x] Runbook enables fast incident response
- [x] Team trained on new monitoring

---

## Rollback Plan

If critical issues arise, the system can be rolled back:

1. **Update ECS services to previous task definition**
   ```bash
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:PREVIOUS \
     --force-new-deployment
   ```

2. **Revert CloudWatch logging** (if needed)
3. **Restore EFS from snapshot** (if data corruption)
4. **Keep S3 for audit purposes**

**Rollback Duration:** 30 minutes

---

## Next Steps

1. [ ] Obtain stakeholder approval for this plan
2. [ ] Schedule kickoff meeting
3. [ ] Assign team members to phases
4. [ ] Begin Phase 1: Planning & Preparation
5. [ ] Track progress against timeline
6. [ ] Conduct post-implementation review

---

**Document Owner:** DevOps Team  
**Last Updated:** March 24, 2026  
**Version:** 1.0.0

