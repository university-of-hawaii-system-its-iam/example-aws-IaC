# Log Rotation Configuration Examples

This directory contains example configuration files for implementing log rotation in the UI and API services.

## Files Provided

### 1. **Dockerfiles** (Updated)
- `/services/api/Dockerfile` - Updated with logrotate installation and configuration
- `/services/ui/Dockerfile` - Updated with logrotate installation and configuration

### 2. **Entrypoint Scripts**
- `/services/api/entrypoint.sh` - API service startup with log rotation scheduling
- `/services/ui/entrypoint.sh` - UI service startup with log rotation scheduling

### 3. **Logrotate Configuration**
- `/services/api/logrotate-api.conf` - Rotation rules for API logs
- `/services/ui/logrotate-ui.conf` - Rotation rules for UI logs

### 4. **Spring Boot Logback Configuration** (Optional)
- `/services/api/logback-spring.xml` - Spring Boot native log rotation for API
- `/services/ui/logback-spring.xml` - Spring Boot native log rotation for UI

### 5. **Infrastructure as Code**
- `/infra/lib/log-archival-stack.ts` - AWS CDK stack for CloudWatch log exports to S3

## Quick Start

### Option 1: Using Logrotate (Recommended)

1. Ensure your source repositories have these files:
   ```
   services/api/
   ├── Dockerfile
   ├── entrypoint.sh
   ├── logrotate-api.conf
   └── logback-spring.xml (optional)
   
   services/ui/
   ├── Dockerfile
   ├── entrypoint.sh
   ├── logrotate-ui.conf
   └── logback-spring.xml (optional)
   ```

2. Update your Dockerfile COPY commands to include configuration files:
   ```dockerfile
   COPY entrypoint.sh /app/entrypoint.sh
   COPY logrotate-api.conf /etc/logrotate.d/api
   COPY logback-spring.xml /app/logback-spring.xml
   RUN chmod +x /app/entrypoint.sh
   ```

3. Docker images will now:
   - Rotate logs daily
   - Compress logs after 1 day
   - Move rotated logs to `/logs/Archive`
   - Delete logs older than 30 days
   - Run rotation check every 6 hours

### Option 2: Using Spring Boot Native Rotation

If you prefer to use Spring Boot's built-in rotation instead of logrotate:

1. Add logback-spring.xml to your Spring Boot classpath
2. Update application.properties:
   ```properties
   logging.config=classpath:logback-spring.xml
   logging.file.name=/var/log/application/api/application.log
   ```

### Option 3: Using AWS Infrastructure

1. Add LogArchivalStack to your CDK app:
   ```typescript
   // infra/bin/app.ts
   import { LogArchivalStack } from '../lib/log-archival-stack';
   
   const app = new cdk.App();
   // ... other stacks ...
   new LogArchivalStack(app, 'uh-groupings-log-archival');
   ```

2. Deploy:
   ```bash
   cd infra
   npm install
   cdk deploy
   ```

## Log File Layout

After implementation, your logs will be organized as:

```
/var/log/application/
├── api/
│   ├── application.log           (current log file)
│   └── application.log.1.gz      (previous day, compressed)
└── ui/
    ├── application.log           (current log file)
    └── application.log.1.gz      (previous day, compressed)

/logs/Archive/
├── application-20260321.1.log.gz (API logs from March 21)
├── application-20260320.1.log.gz (API logs from March 20)
├── application-20260321.2.log.gz (UI logs from March 21)
└── application-20260320.2.log.gz (UI logs from March 20)
```

## EFS Mount Configuration

In your ECS task definition, mount the EFS volume:

```typescript
const efsVolumeConfiguration: ecs.EfsVolumeConfiguration = {
  fileSystemId: efsFileSystem.fileSystemId,
  transitEncryption: 'ENABLED',
};

taskDef.addVolume({
  name: 'logs-volume',
  efsVolumeConfiguration,
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

## Monitoring and Verification

### Check Log Rotation Status
```bash
# Inside container
logrotate -d -f /etc/logrotate.d/api  # Test run
logrotate -f /etc/logrotate.d/api     # Force rotation

# Check archive directory
ls -lah /logs/Archive/
du -sh /logs/Archive/
```

### CloudWatch Metrics
The infrastructure stack creates CloudWatch log groups:
- `/ecs/uh-groupings/api` (7-day retention)
- `/ecs/uh-groupings/ui` (7-day retention)

### S3 Verification
CloudWatch logs are exported daily to S3:
```
s3://uh-groupings-logs-archive-{account-id}/
├── cloudwatch-logs/
│   ├── /ecs/uh-groupings/api/
│   │   └── 2026/03/24/...
│   └── /ecs/uh-groupings/ui/
│       └── 2026/03/24/...
```

## Customization

### Adjust Rotation Frequency
In logrotate config files, change:
- `daily` → `weekly` (every 7 days)
- `rotate 7` → `rotate 3` (keep 3 rotations instead of 7)

### Adjust Maximum Log Age
In logrotate config:
```
maxage 30  # Delete logs older than 30 days
```

### Adjust Spring Boot Settings
In logback-spring.xml:
```xml
<maxFileSize>500MB</maxFileSize>      <!-- Rotate at 500MB -->
<maxHistory>10</maxHistory>            <!-- Keep 10 days -->
<totalSizeCap>5GB</totalSizeCap>       <!-- Cap at 5GB total -->
```

## Troubleshooting

### Logs not rotating
- Check logrotate syntax: `logrotate -d -f /etc/logrotate.d/api`
- Verify file patterns match: `ls -la /var/log/application/api/`
- Check permissions on `/logs/Archive`

### Permission denied errors
- Ensure entrypoint.sh is executable: `chmod +x /app/entrypoint.sh`
- Check that `/logs/Archive` has write permissions: `chmod 755 /logs/Archive`

### High disk usage
- Reduce `rotate` count in logrotate config
- Reduce `maxage` value
- Check for uncompressed files taking up space
- Monitor with: `du -sh /var/log/application/* /logs/Archive/`

## References

- [Logrotate Manual](https://linux.die.net/man/8/logrotate)
- [Spring Boot Logging Documentation](https://docs.spring.io/spring-boot/docs/current/reference/html/features.html#features.logging)
- [Logback Configuration Reference](https://logback.qos.ch/manual/configuration.html)
- [AWS CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)

