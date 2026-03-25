# Log Rotation Implementation Guide

## Summary

Log rotation with archival to `/logs/Archive` has been implemented in this AWS Fargate environment using a **hybrid approach**:

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

## What Was Implemented

### **Files Created/Modified**

#### Container Configuration
```
services/api/
├── Dockerfile (UPDATED)
├── entrypoint.sh (NEW)
├── logrotate-api.conf (NEW)
└── logback-spring.xml (NEW - optional)

services/ui/
├── Dockerfile (UPDATED)
├── entrypoint.sh (NEW)
├── logrotate-ui.conf (NEW)
└── logback-spring.xml (NEW - optional)
```

#### Infrastructure
```
infra/lib/
└── log-archival-stack.ts (NEW)
```

#### Documentation
```
docs/
├── LOG_ROTATION.md (detailed guide)
├── IMPLEMENTATION_SUMMARY.md (this file)
├── DEPLOYMENT_CHECKLIST.md (step-by-step)
├── ARCHITECTURE_DIAGRAMS.md (visual)
├── QUICK_REFERENCE.md (lookup)
└── README_LOG_ROTATION.md (quick start)
```

---

## How It Works

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

## Configuration Details

### **Logrotate Configuration** (`logrotate-api.conf`)

```conf
/var/log/application/api/*.log {
    daily                    # Rotate when logrotate runs daily
    rotate 7                 # Keep 7 rotated versions
    compress                 # Compress with gzip
    delaycompress            # Compress on next rotation (prevents errors)
    missingok                # Don't error if log missing
    notifempty               # Don't rotate if file is empty
    create 0640 root root    # New file permissions
    maxage 30                # Delete files >30 days old
    olddir /logs/Archive     # Move to archive directory
    dateext                  # Add date to filename (not sequential numbers)
    dateformat -%Y%m%d       # Format: -20260324
}
```

**Result:**
- Fresh logs: `/var/log/application/api/application.log`
- Rotated logs: `/logs/Archive/application-20260323.1.log.gz`

### **Spring Boot Configuration** (`logback-spring.xml`)

```xml
<appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
    <file>/var/log/application/api/application.log</file>
    
    <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
        <fileNamePattern>/logs/Archive/application-%d{yyyy-MM-dd}.%i.log.gz</fileNamePattern>
        <maxFileSize>100MB</maxFileSize>      <!-- Rotate at 100MB -->
        <maxHistory>7</maxHistory>             <!-- Keep 7 days -->
        <totalSizeCap>1GB</totalSizeCap>       <!-- Cap total size -->
    </rollingPolicy>
</appender>
```

**Advantages:**
- Spring Boot manages rotation (no external tool needed)
- Automatic archival to `/logs/Archive`
- Size and time-based triggers
- Integrated with Spring Boot logging

### **CloudWatch Configuration** (`log-archival-stack.ts`)

```typescript
const apiLogGroup = new logs.LogGroup(this, 'api-log-group', {
  logGroupName: '/ecs/uh-groupings/api',
  retention: logs.RetentionDays.SEVEN_DAYS,
  removalPolicy: cdk.RemovalPolicy.RETAIN,
});
```

**Features:**
- 7-day retention in CloudWatch
- Logs still available via AWS Console
- CloudWatch Insights for querying
- Alarms and metrics available

### **S3 Lifecycle Policy**

```typescript
lifecycleRules: [
  {
    transitions: [
      {
        storageClass: s3.StorageClass.GLACIER,
        transitionAfter: cdk.Duration.days(90),
      },
      {
        storageClass: s3.StorageClass.DEEP_ARCHIVE,
        transitionAfter: cdk.Duration.days(180),
      },
    ],
    expiration: cdk.Duration.days(2555), // 7 years
  },
]
```

**Storage Costs:**
- Days 0-90: ~$0.023/GB/month (Standard)
- Days 90-180: ~$0.004/GB/month (Glacier)
- Days 180+: ~$0.00099/GB/month (Deep Archive)
- Day 2555: Deleted (retention expired)

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

1. Add to `infra/bin/app.ts`:
   ```typescript
   import { LogArchivalStack } from '../lib/log-archival-stack';
   
   const logArchivalStack = new LogArchivalStack(app, 'uh-groupings-log-archival');
   ```

2. Deploy:
   ```bash
   cd infra
   npm install
   cdk deploy
   ```

### **Step 3: Configure ECS Task Definition**
Update to mount EFS volume:

```typescript
const efsVolume = taskDef.addVolume({
  name: 'logs-volume',
  efsVolumeConfiguration: {
    fileSystemId: efsFileSystem.fileSystemId,
    transitEncryption: 'ENABLED',
  },
});

container.addMountPoints({
  sourceVolume: 'logs-volume',
  containerPath: '/var/log/application',
  readOnly: false,
});

container.addMountPoints({
  sourceVolume: 'logs-volume',
  containerPath: '/logs',
  readOnly: false,
});
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

| Issue | Cause | Solution |
|-------|-------|----------|
| Logs not rotating | Pattern mismatch | Check: `ls /var/log/application/api/*.log` |
| Permission denied on archive | Wrong permissions | Run: `chmod 755 /logs/Archive` |
| High disk usage | Rotation not running | Check: `logrotate -d /etc/logrotate.d/api` |
| CloudWatch logs missing | ECS task not configured | Verify task definition has log driver |
| S3 export failing | Lambda permissions | Check: `aws lambda get-function --function-name export-logs-function` |

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

## Next Steps

1. **Copy files to service repositories**
   - Transfer all container configuration files
   - Update Dockerfiles with COPY commands

2. **Test locally with Docker**
   ```bash
   docker build -t api:test .
   docker run --name api-test -v logs:/logs api:test
   # Wait 6+ hours or adjust sleep time in entrypoint.sh for testing
   ```

3. **Deploy to AWS**
   - Update service images in ECR
   - Trigger ECS task update
   - Monitor CloudWatch logs

4. **Verify in production**
   - Check EFS for `/logs/Archive` directory
   - Verify CloudWatch log streams
   - Confirm S3 exports are occurring daily

---

## References

- **Logrotate Manual:** https://linux.die.net/man/8/logrotate
- **Spring Boot Logging:** https://docs.spring.io/spring-boot/docs/current/reference/html/features.html#features.logging
- **Logback Configuration:** https://logback.qos.ch/manual/configuration.html
- **AWS ECS Logging:** https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_cloudwatch_logs.html
- **AWS S3 Lifecycle:** https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html

