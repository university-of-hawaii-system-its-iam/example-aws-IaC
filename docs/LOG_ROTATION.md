# Log Rotation and Archive Strategy

## Executive Summary

Log rotation with archival to `/logs/Archive` is implemented in this AWS Fargate environment using a **hybrid approach**:

### **Three-Tier System**

| Tier | Technology      | Retention  | Purpose                        |
|------|-----------------|------------|--------------------------------|
| **1** | EFS (Local)     | 30 days    | Immediate troubleshooting      |
| **2** | CloudWatch Logs | 7 days     | Real-time monitoring           |
| **3** | S3 Archive      | 7 years    | Compliance & long-term storage |

### **Tier 1: Container-Level Log Rotation (Logrotate + Spring Boot)**
- **Where:** Inside each ECS container
- **What:** Daily log rotation with compression
- **Destination:** `/logs/Archive` (EFS-mounted)
- **Retention:** 7 days rolling, max 30 days
- **Management:** Automatic via entrypoint script

### **Tier 2: Centralized Log Aggregation (CloudWatch)**
- **Where:** AWS CloudWatch Logs
- **What:** Real-time log streaming from ECS tasks
- **Retention:** 7 days (configurable)
- **Use:** Monitoring, alarming, debugging

### **Tier 3: Long-Term Archival (S3)**
- **Where:** Amazon S3
- **What:** Daily export of CloudWatch logs
- **Destination:** S3 with lifecycle policies
- **Retention:** 7 years (cost-optimized via Glacier)
- **Use:** Compliance, auditing, historical analysis

---

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

Update ECS Task Definition in `infra/stacks/app_stack.py`:

```python
# Configure CloudWatch logging
api_log_driver = ecs.LogDriver.aws_logs(
    log_group=logs.LogGroup(self, "api-log-group",
        log_group_name="/ecs/uh-groupings/api",
        retention=logs.RetentionDays.SEVEN_DAYS,
        removal_policy=cdk.RemovalPolicy.RETAIN,
    ),
    stream_prefix="api-task",
)

ui_log_driver = ecs.LogDriver.aws_logs(
    log_group=logs.LogGroup(self, "ui-log-group",
        log_group_name="/ecs/uh-groupings/ui",
        retention=logs.RetentionDays.SEVEN_DAYS,
        removal_policy=cdk.RemovalPolicy.RETAIN,
    ),
    stream_prefix="ui-task",
)
```

#### Export to S3 via Lambda

Create a Lambda function to periodically export CloudWatch logs to S3:

**`infra/stacks/log_archival_stack.py`:**
```python
import aws_cdk as cdk
from aws_cdk import (
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
)
from constructs import Construct


class LogArchivalStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for log archives
        log_archive_bucket = s3.Bucket(self, "log-archive-bucket",
            bucket_name=f"uh-groupings-logs-archive-{cdk.Stack.of(self).account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=cdk.Duration.days(90),
                        ),
                    ],
                    expiration=cdk.Duration.days(2555),  # 7 years
                ),
            ],
        )

        # Lambda function for exporting logs
        export_logs_function = lambda_.Function(self, "export-logs-function",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline(EXPORT_HANDLER_CODE),
            environment={"LOG_BUCKET": log_archive_bucket.bucket_name},
            timeout=cdk.Duration.minutes(5),
        )

        # Grant permissions
        export_logs_function.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["logs:CreateExportTask", "logs:DescribeExportTasks"],
                resources=["*"],
            )
        )
        log_archive_bucket.grant_write(export_logs_function)

        # Schedule daily exports
        rule = events.Rule(self, "export-logs-schedule",
            schedule=events.Schedule.cron(hour="2", minute="0"),
        )
        rule.add_target(targets.LambdaFunction(export_logs_function))
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

Add a sidecar container to ECS task definition in `infra/stacks/app_stack.py`:

```python
# Create a simple logrotate sidecar image
log_rotate_sidecar = ecs.ContainerImage.from_registry(
    "123456789.dkr.ecr.us-east-1.amazonaws.com/logrotate-sidecar:latest"
)

task_def.add_container("log-rotator",
    image=log_rotate_sidecar,
    cpu=64,
    memory_reservation_mib=128,
    essential=False,
    logging=ecs.LogDriver.aws_logs(
        log_group=log_group,
        stream_prefix="log-rotator",
    ),
)
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

```python
from aws_cdk import aws_datasync as datasync

# Create DataSync task from EFS to S3
efs_location = datasync.CfnLocationEFS(self, "efs-source",
    ec2_config=datasync.CfnLocationEFS.Ec2ConfigProperty(
        subnet_arn=vpc.private_subnets[0].subnet_arn,
        security_group_arns=[efs_security_group.security_group_arn],
    ),
    efs_filesystem_arn=efs_file_system.file_system_arn,
    subdirectory="/var/log/application",
)

s3_location = datasync.CfnLocationS3(self, "s3-destination",
    s3_bucket_arn=log_archive_bucket.bucket_arn,
    s3_config=datasync.CfnLocationS3.S3ConfigProperty(
        bucket_access_role_arn=datasync_role.role_arn,
    ),
    subdirectory="/archive",
)

datasync.CfnTask(self, "efs-to-s3-task",
    source_location_arn=efs_location.attr_location_arn,
    destination_location_arn=s3_location.attr_location_arn,
    schedule=datasync.CfnTask.TaskScheduleProperty(
        schedule_expression="cron(0 2 * * ? *)",  # 2 AM UTC daily
    ),
)
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

```python
log_size_alarm = cloudwatch.Alarm(self, "log-size-alarm",
    metric=cloudwatch.Metric(
        namespace="AWS/EFS",
        metric_name="StorageBytes",
        statistic="Average",
        period=cdk.Duration.hours(1),
    ),
    threshold=1099511627776,  # 1TB
    evaluation_periods=1,
    alarm_description="Alert when log size exceeds 1TB",
)
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

---

## How It Works - Step-by-Step

### **Step 1: Container Startup (Logrotate)**
When an ECS task starts:

1. **Entrypoint script executes:**
   ```bash
   #!/bin/sh
   mkdir -p /var/log/application/api /logs/Archive
   logrotate -f /etc/logrotate.d/api  # Force immediate rotation check
   
   # Background: Check rotation every 6 hours
   while true; do
     sleep 21600
     logrotate -f /etc/logrotate.d/api
   done &
   
   # Foreground: Start Java application
   exec java -jar app.jar
   ```

2. **Logrotate rules apply:**
   - **Daily:** Rotates logs when they match the pattern
   - **Compress:** Compresses with gzip (delays until next cycle)
   - **MaxAge:** Deletes files older than 30 days
   - **OldDir:** Moves rotated files to `/logs/Archive`
   - **MaxSize:** Rotates when file exceeds 100MB

3. **Log files are organized:**
   ```
   /var/log/application/api/
   └── application.log (current)
   
   /logs/Archive/
   ├── application-20260323.1.log.gz
   ├── application-20260322.1.log.gz
   └── application-20260321.1.log.gz
   ```

### **Step 2: Spring Boot Logging (Optional)**
If using logback-spring.xml:

- Spring Boot writes to `/var/log/application/{api,ui}/application.log`
- Logback detects when log file reaches 100MB
- Automatically rolls to `/logs/Archive/application-YYYYMMDD.N.log.gz`
- **Advantage:** Works even without external logrotate

### **Step 3: CloudWatch Log Aggregation**
ECS task definition sends logs to CloudWatch:

```
Container STDOUT/STDERR → CloudWatch Logs → /ecs/uh-groupings/{api,ui}
```

- Real-time log streaming
- CloudWatch Insights queries available
- 7-day retention (configurable)
- CloudWatch alarms for errors

### **Step 4: S3 Archival (Daily)**
Lambda function runs daily at 2 AM UTC:

```
CloudWatch Logs → Lambda Export Task → S3 Bucket
                                    ↓
                              s3://uh-groupings-logs-archive-{account}/
                              cloudwatch-logs/{service}/2026/03/24/
```

- **Lifecycle policies:** 
  - Day 0-90: Standard storage
  - Day 90-180: Glacier (cheaper, longer retrieval time)
  - Day 180+: Deep Archive (cheapest, ~12 hour retrieval)
  - Day 2555: Deleted (7-year compliance window)

---

## Directory Structure After Implementation

```
/var/log/application/
├── api/
│   ├── application.log              (current, ~0-100MB)
│   ├── application.log.1.gz         (previous rotation, compressed)
│   └── application.log.2.gz         (older rotation, compressed)
│
└── ui/
    ├── application.log              (current, ~0-100MB)
    ├── application.log.1.gz         (previous rotation, compressed)
    └── application.log.2.gz         (older rotation, compressed)

/logs/Archive/
├── application-20260324.1.log.gz    (API logs from today)
├── application-20260324.2.log.gz    (UI logs from today)
├── application-20260323.1.log.gz    (API logs yesterday)
├── application-20260323.2.log.gz    (UI logs yesterday)
└── ... (up to 30 days)

S3: s3://uh-groupings-logs-archive-{account-id}/
├── cloudwatch-logs/
│   ├── /ecs/uh-groupings/api/
│   │   └── 2026/03/24/
│   │       └── {export-task-id}
│   │
│   └── /ecs/uh-groupings/ui/
│       └── 2026/03/24/
│           └── {export-task-id}
```

---

## Deployment Steps

### **Step 1: Update Service Repositories**
In your `uh-groupings-api` and `uh-groupings-ui` repositories:

1. Copy these files:
   - `entrypoint.sh`
   - `logrotate-{service}.conf`
   - `logback-spring.xml` (optional)

2. Update Dockerfile to copy them:
   ```dockerfile
   COPY entrypoint.sh /app/entrypoint.sh
   COPY logrotate-api.conf /etc/logrotate.d/api
   COPY logback-spring.xml /app/logback-spring.xml
   RUN chmod +x /app/entrypoint.sh
   
   ENTRYPOINT ["/app/entrypoint.sh"]
   ```

3. Rebuild and push images to ECR

### **Step 2: Update Infrastructure (Optional)**
To enable CloudWatch export to S3:

1. Add to `infra/app.py`:
   ```python
   from stacks.log_archival_stack import LogArchivalStack
   
   LogArchivalStack(app, "LogArchivalStack", env=env)
   ```

2. Deploy:
   ```bash
   cd infra
   pip install -r requirements.txt
   cdk deploy
   ```

### **Step 3: Configure ECS Task Definition**
Update to mount EFS volume:

```python
task_def.add_volume(
    name="logs-volume",
    efs_volume_configuration=ecs.EfsVolumeConfiguration(
        file_system_id=efs_file_system.file_system_id,
        transit_encryption="ENABLED",
    ),
)

container.add_mount_points(
    ecs.MountPoint(
        source_volume="logs-volume",
        container_path="/var/log/application",
        read_only=False,
    ),
)

container.add_mount_points(
    ecs.MountPoint(
        source_volume="logs-volume",
        container_path="/logs",
        read_only=False,
    ),
)
```

### **Step 4: Update Service Configuration**
In `application.properties` (optional):

```properties
# Enable logback configuration
logging.config=classpath:logback-spring.xml
logging.file.name=/var/log/application/api/application.log
logging.level.root=INFO
logging.level.com.uh.groupings=DEBUG
```

---

## Monitoring & Troubleshooting

### **Verify Rotation is Working**

```bash
# Inside container
logrotate -d -f /etc/logrotate.d/api  # Dry run
logrotate -f /etc/logrotate.d/api     # Force rotation

# Check archive directory
ls -lah /logs/Archive/
du -sh /logs/Archive/

# Check CloudWatch
aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `uh-groupings`)]'

# Check S3
aws s3 ls s3://uh-groupings-logs-archive-{account-id}/cloudwatch-logs/
```

### **Common Issues & Solutions**

| Issue                        | Cause                   | Solution                                                              |
|------------------------------|-------------------------|-----------------------------------------------------------------------|
| Logs not rotating            | Pattern mismatch        | Check: `ls /var/log/application/api/*.log`                            |
| Permission denied on archive | Wrong permissions       | Run: `chmod 755 /logs/Archive`                                        |
| High disk usage              | Rotation not running    | Check: `logrotate -d /etc/logrotate.d/api`                            |
| CloudWatch logs missing      | ECS task not configured | Verify task definition has log driver                                 |
| S3 export failing            | Lambda permissions      | Check: `aws lambda get-function --function-name export-logs-function` |

### **CloudWatch Queries**

```
# Find error patterns
fields @timestamp, @message
| filter @message like /ERROR/
| stats count() as error_count by bin(5m)

# Log volume by service
fields @log
| stats count() as log_count by @log
| filter ispresent(@log)

# Recent errors
fields @timestamp, @message, @logStream
| filter @message like /Exception/
| sort @timestamp desc
| limit 100
```

---

## Best Practices

### **1. Monitoring**
- Set up CloudWatch alarms for `/logs/Archive` disk usage
- Monitor logrotate execution success via CloudWatch Insights
- Alert on high log volume or errors

### **2. Retention Policy**
- **Hot logs** (current): In EFS, searchable immediately
- **Warm logs** (7 days): In CloudWatch, queryable
- **Cold logs** (7+ days): In S3 Standard, cheaper storage
- **Archive logs** (180+ days): In Glacier/Deep Archive, compliance

### **3. Cost Optimization**
- EFS: $0.30/GB/month (don't store more than needed)
- CloudWatch: $0.50/GB ingested (7-day retention is cost-effective)
- S3 Glacier: $0.004/GB/month (90%+ savings vs Standard)
- Deep Archive: $0.00099/GB/month (even better after 180 days)

### **4. Security**
- S3 bucket is blocked from public access
- CloudWatch logs encrypted at rest
- EFS encrypted in transit
- IAM roles restrict service access

### **5. Compliance**
- 7-year retention in S3/Glacier/Deep Archive
- Immutable versioning on S3 bucket
- CloudTrail logs all bucket access (optional)

---

## References

- **Logrotate Manual:** https://linux.die.net/man/8/logrotate
- **Spring Boot Logging:** https://docs.spring.io/spring-boot/docs/current/reference/html/features.html#features.logging
- **Logback Configuration:** https://logback.qos.ch/manual/configuration.html
- **AWS ECS Logging:** https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_cloudwatch_logs.html
- **AWS S3 Lifecycle:** https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html
