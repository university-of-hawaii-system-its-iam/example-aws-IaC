# Log Rotation and Archive Strategy

This document describes how to implement log rotation and archival for the UI and API services in the AWS Fargate environment.

## Overview

The current setup writes application logs to EFS-mounted directories:
- **API logs:** `/var/log/application/api/`
- **UI logs:** `/var/log/application/ui/`

This guide provides multiple approaches for rotating logs and archiving older files to `/logs/Archive`.

---

## Approach 1: `logrotate` (Recommended for EFS-Backed Logs)

### Why logrotate?
- Industry-standard log rotation tool in Linux
- Works well with EFS and persistent storage
- Simple configuration
- Minimal performance impact
- No application changes required

### Implementation Steps

#### 1.1 Update Dockerfiles

Add logrotate to both Dockerfiles and create configuration files:

**For `/services/api/Dockerfile`:**
```dockerfile
# Stage 1: Build Stage
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy source code
COPY . .

# Build the Spring Boot application
RUN mvn clean package -DskipTests

# Stage 2: Runtime Stage
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Install logrotate
RUN apk add --no-cache logrotate

# Copy the built JAR from builder stage
COPY --from=builder /app/target/*.jar app.jar

# Create log directory and archive directory
RUN mkdir -p /var/log/application/api /logs/Archive && \
    chmod 755 /var/log/application/api /logs/Archive

# Copy logrotate configuration
COPY logrotate-api.conf /etc/logrotate.d/api

# Expose port
EXPOSE 8080

# Health check (Spring Boot actuator endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# Start the application with log rotation
CMD ["/bin/sh", "-c", "(logrotate -f /etc/logrotate.d/api) && exec java -jar app.jar"]
```

**For `/services/ui/Dockerfile`:**
```dockerfile
# Stage 1: Build Stage
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy source code
COPY . .

# Build the Spring Boot application
RUN mvn clean package -DskipTests

# Stage 2: Runtime Stage
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Install logrotate
RUN apk add --no-cache logrotate

# Copy the built JAR from builder stage
COPY --from=builder /app/target/*.jar app.jar

# Create log directory and archive directory
RUN mkdir -p /var/log/application/ui /logs/Archive && \
    chmod 755 /var/log/application/ui /logs/Archive

# Copy logrotate configuration
COPY logrotate-ui.conf /etc/logrotate.d/ui

# Expose port
EXPOSE 3000

# Health check (Spring Boot actuator endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/actuator/health || exit 1

# Start the application with log rotation
CMD ["/bin/sh", "-c", "(logrotate -f /etc/logrotate.d/ui) && exec java -jar app.jar"]
```

#### 1.2 Create Logrotate Configuration Files

**`/services/api/logrotate-api.conf`:**
```
/var/log/application/api/*.log {
    daily                          # Rotate daily
    rotate 7                       # Keep 7 rotated logs
    compress                       # Compress rotated logs (gzip)
    delaycompress                  # Delay compression until next rotation
    missingok                      # Don't error if log file is missing
    notifempty                     # Don't rotate empty log files
    create 0640 root root          # Create new log file with these permissions
    maxage 30                      # Delete logs older than 30 days
    olddir /logs/Archive           # Move rotated logs to archive directory
    postrotate
        # Optional: Send signal to Java process to reopen log files
        kill -HUP `cat /var/run/application.pid 2>/dev/null` 2>/dev/null || true
    endscript
}
```

**`/services/ui/logrotate-ui.conf`:**
```
/var/log/application/ui/*.log {
    daily                          # Rotate daily
    rotate 7                       # Keep 7 rotated logs
    compress                       # Compress rotated logs (gzip)
    delaycompress                  # Delay compression until next rotation
    missingok                      # Don't error if log file is missing
    notifempty                     # Don't rotate empty log files
    create 0640 root root          # Create new log file with these permissions
    maxage 30                      # Delete logs older than 30 days
    olddir /logs/Archive           # Move rotated logs to archive directory
    postrotate
        # Optional: Send signal to Java process to reopen log files
        kill -HUP `cat /var/run/application.pid 2>/dev/null` 2>/dev/null || true
    endscript
}
```

#### 1.3 Configure Spring Boot Logging (Optional but Recommended)

Configure `application.properties` or `application.yml` to use a specific log file:

**`application.properties`:**
```properties
# API Service
logging.file.name=/var/log/application/api/application.log
logging.file.max-size=100MB
logging.file.max-history=7
logging.file.total-size-cap=1GB
logging.level.root=INFO
logging.level.com.uh.groupings=DEBUG
```

**`application.yml`:**
```yaml
logging:
  file:
    name: /var/log/application/api/application.log
    max-size: 100MB
    max-history: 7
    total-size-cap: 1GB
  level:
    root: INFO
    com.uh.groupings: DEBUG
```

#### 1.4 Schedule Logrotate with Cron

For periodic rotation every 6 hours, update the Dockerfile CMD:

```dockerfile
CMD ["/bin/sh", "-c", "echo '0 */6 * * * logrotate -f /etc/logrotate.d/api' | crontab - && crond && exec java -jar app.jar"]
```

Or use a shell script:

**`/services/api/entrypoint.sh`:**
```bash
#!/bin/sh
set -e

# Run logrotate on container startup
logrotate -f /etc/logrotate.d/api

# Schedule logrotate to run every 6 hours
(while true; do
    sleep 21600  # 6 hours in seconds
    logrotate -f /etc/logrotate.d/api
done) &

# Start the Java application
exec java -jar app.jar
```

---

## Approach 2: Spring Boot Built-in Log Rotation

### Why Spring Boot Built-in?
- No external dependencies beyond logback
- Configured entirely in application properties
- Works across all environments
- Easier to version control with application code

### Implementation

Add the following to your Spring Boot `application.properties`:

```properties
# Logging file configuration
logging.file.name=/var/log/application/api/application.log

# Logback rolling file appender configuration
logging.config=classpath:logback-spring.xml  # Use Spring-specific logback config
logging.level.root=INFO
logging.level.com.uh.groupings=DEBUG

# Spring Boot log rotation (if using logback)
logging.file.max-size=100MB
logging.file.max-history=7
logging.file.total-size-cap=1GB
```

Or create a `logback-spring.xml` configuration file:

**`src/main/resources/logback-spring.xml`:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <property name="LOG_FILE" value="/var/log/application/api/application.log"/>
    <property name="LOG_ARCHIVE" value="/logs/Archive/application-%d{yyyy-MM-dd}.%i.log.gz"/>
    <property name="LOG_FILE_MAX_SIZE" value="100MB"/>
    <property name="LOG_FILE_MAX_HISTORY" value="7"/>
    <property name="LOG_TOTAL_SIZE_CAP" value="1GB"/>

    <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>${LOG_FILE}</file>
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>

        <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
            <fileNamePattern>${LOG_ARCHIVE}</fileNamePattern>
            <maxFileSize>${LOG_FILE_MAX_SIZE}</maxFileSize>
            <maxHistory>${LOG_FILE_MAX_HISTORY}</maxHistory>
            <totalSizeCap>${LOG_TOTAL_SIZE_CAP}</totalSizeCap>
        </rollingPolicy>
    </appender>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <root level="INFO">
        <appender-ref ref="FILE"/>
        <appender-ref ref="STDOUT"/>
    </root>

    <logger name="com.uh.groupings" level="DEBUG"/>
</configuration>
```

---

## Approach 3: CloudWatch Logs with S3 Export

### Why CloudWatch Logs Export?
- Centralized log management
- Real-time log aggregation
- Long-term retention in S3
- Built-in AWS monitoring and alarms
- No changes to containers required

### Implementation

Update ECS Task Definition in `infra/lib/app-stack.ts`:

```typescript
// Configure CloudWatch logging
const apiLogDriver = ecs.LogDriver.awsLogs({
  logGroup: new logs.LogGroup(this, 'api-log-group', {
    logGroupName: '/ecs/uh-groupings/api',
    retention: logs.RetentionDays.SEVEN_DAYS,
    removalPolicy: cdk.RemovalPolicy.RETAIN,
  }),
  streamPrefix: 'api-task',
});

const uiLogDriver = ecs.LogDriver.awsLogs({
  logGroup: new logs.LogGroup(this, 'ui-log-group', {
    logGroupName: '/ecs/uh-groupings/ui',
    retention: logs.RetentionDays.SEVEN_DAYS,
    removalPolicy: cdk.RemovalPolicy.RETAIN,
  }),
  streamPrefix: 'ui-task',
});
```

#### Export to S3 via Lambda

Create a Lambda function to periodically export CloudWatch logs to S3:

**`infra/lib/log-archival-stack.ts`:**
```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export class LogArchivalStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Create S3 bucket for log archives
    const logArchiveBucket = new s3.Bucket(this, 'log-archive-bucket', {
      bucketName: `uh-groupings-logs-archive-${cdk.Stack.of(this).account}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      lifecycleRules: [
        {
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(90),
            },
          ],
          expiration: cdk.Duration.days(2555), // 7 years
        },
      ],
    });

    // Lambda function for exporting logs
    const exportLogsFunction = new lambda.Function(this, 'export-logs-function', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/export-logs'),
      environment: {
        LOG_BUCKET: logArchiveBucket.bucketName,
      },
      timeout: cdk.Duration.minutes(5),
    });

    // Grant permissions
    exportLogsFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'logs:CreateExportTask',
          'logs:DescribeExportTasks',
          'logs:StartQuery',
        ],
        resources: ['*'],
      })
    );

    logArchiveBucket.grantWrite(exportLogsFunction);

    // Schedule daily exports
    const rule = new events.Rule(this, 'export-logs-schedule', {
      schedule: events.Schedule.cron({
        hour: '2',      // 2 AM UTC
        minute: '0',
      }),
    });

    rule.addTarget(new targets.LambdaTarget(exportLogsFunction));
  }
}
```

**`lambda/export-logs/index.py`:**
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
    
    # Export logs from previous day
    end_time = int(datetime.now().timestamp() * 1000)
    start_time = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)
    
    for log_group in log_groups:
        try:
            response = logs_client.create_export_task(
                logGroupName=log_group,
                fromTime=start_time,
                to=end_time,
                destination=s3_bucket,
                destinationPrefix=f"logs/{log_group}/{datetime.now().strftime('%Y/%m/%d')}"
            )
            print(f"Export task created for {log_group}: {response['taskId']}")
        except Exception as e:
            print(f"Error exporting logs for {log_group}: {str(e)}")
    
    return {
        'statusCode': 200,
        'body': json.dumps('Log export completed')
    }
```

---

## Approach 4: Sidecar Container for Log Rotation

### Why Sidecar?
- Separates log rotation concerns from application
- Works with existing application code
- Centralized configuration
- Scalable across all ECS tasks

### Implementation

Add a sidecar container to ECS task definition in `infra/lib/app-stack.ts`:

```typescript
// Create a simple logrotate sidecar image
const logRotateSidecar = ecs.ContainerImage.fromRegistry(
  '123456789.dkr.ecr.us-east-1.amazonaws.com/logrotate-sidecar:latest'
);

taskDef.addContainer('log-rotator', {
  image: logRotateSidecar,
  cpu: 64,
  memoryReservationMiB: 128,
  essential: false,
  logging: ecs.LogDriver.awsLogs({
    logGroup: logGroup,
    streamPrefix: 'log-rotator',
  }),
});
```

**Sidecar Dockerfile** (`services/log-rotator/Dockerfile`):
```dockerfile
FROM alpine:latest

RUN apk add --no-cache logrotate

COPY logrotate-config /etc/logrotate.d/

CMD ["sh", "-c", "while true; do logrotate -f /etc/logrotate.d/*; sleep 21600; done"]
```

---

## Approach 5: AWS DataSync for Automated Archival

### Why DataSync?
- AWS-native solution
- Automatic scheduled transfers
- Built-in monitoring
- No application changes
- Cost-effective for large volumes

### Implementation

Add DataSync configuration to infrastructure:

```typescript
import * as datasync from 'aws-cdk-lib/aws-datasync';

// Create DataSync task from EFS to S3
const efsLocation = new datasync.EfsLocation(this, 'efs-source', {
  ec2Config: new datasync.Ec2Config({
    subnetId: vpc.privateSubnets[0].subnetId,
    securityGroupIds: [efsSecurityGroup.securityGroupId],
  }),
  fileSystemId: efsFileSystem.fileSystemId,
  subdirectory: '/var/log/application',
});

const s3Location = new datasync.S3Location(this, 's3-destination', {
  bucket: logArchiveBucket,
  prefix: 'archive',
});

new datasync.Task(this, 'efs-to-s3-task', {
  sourceLocation: efsLocation,
  destinationLocation: s3Location,
  schedule: {
    expression: 'cron(0 2 * * ? *)', // 2 AM UTC daily
  },
  options: {
    atime: datasync.Atime.BEST_EFFORT,
    mtime: datasync.Mtime.PRESERVE,
    deleteMode: datasync.DeleteMode.REMOVE,  // Delete after copy
  },
});
```

---

## Recommended Approach Summary

| Approach | Pros | Cons | Best For |
|----------|------|------|----------|
| **Logrotate** | Standard, reliable, no app changes | Requires Docker modification | EFS-backed logs |
| **Spring Boot Built-in** | Integrated, version controlled | Spring-specific, code dependency | Spring Boot apps |
| **CloudWatch + S3** | Centralized, AWS-native, monitored | Costs, eventual consistency | Long-term retention |
| **Sidecar Container** | Clean separation, scalable | Additional container overhead | Multi-service deployments |
| **AWS DataSync** | Automated, efficient, no code change | Cost, AWS-specific | Large log volumes |

### **Recommended: Approach 1 (Logrotate) + Approach 3 (CloudWatch)**

Combine logrotate for local log management with CloudWatch for:
- Real-time monitoring
- S3 export for long-term retention
- CloudWatch alarms for errors

This provides:
- ✅ Fast local log rotation
- ✅ Centralized log aggregation
- ✅ Long-term archival
- ✅ Built-in AWS monitoring
- ✅ Easy troubleshooting

---

## Configuration Parameters

### Logrotate Tuning for Different Workloads

**High-Volume Services (>100MB/day):**
```
daily
rotate 3
compress
delaycompress
maxage 14
olddir /logs/Archive
size 100M
```

**Medium-Volume Services (10-100MB/day):**
```
daily
rotate 7
compress
delaycompress
maxage 30
olddir /logs/Archive
```

**Low-Volume Services (<10MB/day):**
```
weekly
rotate 12
compress
delaycompress
maxage 90
olddir /logs/Archive
```

### Spring Boot Logging Tuning

```properties
# For high-volume logs
logging.file.max-size=500MB
logging.file.max-history=5
logging.file.total-size-cap=2GB

# For standard logs
logging.file.max-size=100MB
logging.file.max-history=7
logging.file.total-size-cap=1GB

# For low-volume logs
logging.file.max-size=10MB
logging.file.max-history=30
logging.file.total-size-cap=500MB
```

---

## Monitoring and Alerting

### CloudWatch Alarms for Log Size

```typescript
const logSizeAlarm = new cloudwatch.Alarm(this, 'log-size-alarm', {
  metric: new cloudwatch.Metric({
    namespace: 'AWS/EFS',
    metricName: 'StorageBytes',
    statistic: 'Average',
    period: cdk.Duration.hours(1),
  }),
  threshold: 1099511627776, // 1TB
  evaluationPeriods: 1,
  alarmDescription: 'Alert when log size exceeds 1TB',
});
```

### Custom Metrics for Rotation Success

Monitor logrotate execution with custom CloudWatch metrics in your entrypoint script:

```bash
if logrotate -f /etc/logrotate.d/api; then
  aws cloudwatch put-metric-data \
    --namespace "LogRotation" \
    --metric-name "RotationSuccess" \
    --value 1
else
  aws cloudwatch put-metric-data \
    --namespace "LogRotation" \
    --metric-name "RotationFailure" \
    --value 1
fi
```

---

## Troubleshooting

### Common Issues

1. **Permission Denied on `/logs/Archive`**
   - Solution: Ensure directories are created with correct permissions in Dockerfile
   - `RUN mkdir -p /logs/Archive && chmod 755 /logs/Archive`

2. **Logs Not Rotating**
   - Check logrotate configuration syntax: `logrotate -d -f /etc/logrotate.d/api`
   - Verify file matching patterns: `/var/log/application/api/*.log`
   - Check disk space availability

3. **EFS Write Failures**
   - Verify EFS security group allows NFS (port 2049)
   - Check ECS task IAM role has EFS permissions
   - Monitor EFS performance metrics in CloudWatch

4. **High Archive Disk Usage**
   - Reduce `rotate` count
   - Enable compression (`compress`)
   - Reduce `maxage` value
   - Consider S3 export instead

### Debug Commands

```bash
# Check logrotate configuration
logrotate -d -f /etc/logrotate.d/api

# Manually run rotation
logrotate -f /etc/logrotate.d/api

# Check EFS mount status
df -h | grep /var/log

# Monitor log sizes
du -sh /var/log/application/*

# Check archive directory
ls -lah /logs/Archive/
```


