# Quick Reference Guide: Log Rotation

## TL;DR - What Was Implemented

✅ **Three-tier log management system:**
1. **Local rotation** (EFS) - Daily, 30-day retention
2. **Real-time aggregation** (CloudWatch) - 7-day queryable logs
3. **Long-term archive** (S3) - 7-year compliance retention

---

## Files Provided

| File | Purpose | Location |
|------|---------|----------|
| `entrypoint.sh` | Starts app + schedules logrotate | `/services/{api,ui}/` |
| `logrotate-*.conf` | Rotation rules (daily, archive to /logs/Archive) | `/services/{api,ui}/` |
| `logback-spring.xml` | Spring Boot log configuration (optional) | `/services/{api,ui}/` |
| `Dockerfile` | Updated with logrotate + volumes | `/services/{api,ui}/` |
| `log-archival-stack.ts` | AWS CDK for S3 + CloudWatch export | `/infra/lib/` |
| `LOG_ROTATION.md` | Detailed configuration guide | `/docs/` |
| `IMPLEMENTATION_SUMMARY.md` | Complete how-it-works guide | `/docs/` |
| `DEPLOYMENT_CHECKLIST.md` | Step-by-step deployment | `/docs/` |
| `ARCHITECTURE_DIAGRAMS.md` | Visual architecture & flows | `/docs/` |

---

## How Logs Flow

```
Application → Logfile → Logrotate → /logs/Archive (EFS)
           ↓                                    ↓
      STDOUT/STDERR                      CloudWatch
           ↓                                    ↓
      CloudWatch Logs ←────────────────────────┘
           ↓
      Lambda (daily)
           ↓
        S3 Bucket
```

---

## Key Configuration Points

### Rotation Schedule
- **Frequency:** Daily (checked every 6 hours by entrypoint)
- **Size trigger:** 100MB
- **Compression:** gzip (delayed 1 rotation cycle)
- **Retention:** 7 days on disk, max 30 days total
- **Archive location:** `/logs/Archive/`

### File Naming
```
Current:   /var/log/application/api/application.log
Rotated:   /var/log/application/api/application.log.1.gz
Archived:  /logs/Archive/application-20260324.1.log.gz
S3:        s3://bucket/cloudwatch-logs/api/2026/03/24/
```

### CloudWatch Retention
- **7-day retention** (queryable)
- **Daily export** to S3 (2 AM UTC)
- **S3 lifecycle:** Standard → Glacier (90d) → Deep Archive (180d) → Delete (7y)

---

## How to Deploy

### Quick Start (Recommended Order)

1. **Add files to service repositories:**
   ```bash
   # In uh-groupings-api repo
   cp services/api/entrypoint.sh .
   cp services/api/logrotate-api.conf .
   cp services/api/logback-spring.xml src/main/resources/
   ```

2. **Update Dockerfile:**
   ```dockerfile
   RUN apk add --no-cache logrotate
   RUN mkdir -p /var/log/application/api /logs/Archive && chmod 755 /var/log/application/api /logs/Archive
   COPY entrypoint.sh /app/entrypoint.sh
   COPY logrotate-api.conf /etc/logrotate.d/api
   RUN chmod +x /app/entrypoint.sh
   ENTRYPOINT ["/app/entrypoint.sh"]
   ```

3. **Push to GitHub & trigger build:**
   - Commit changes
   - Tag with version (e.g., `v1.2.0`)
   - GitHub Actions builds and pushes to ECR

4. **Update ECS service:**
   ```bash
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:latest \
     --force-new-deployment
   ```

5. **Deploy infrastructure (optional):**
   ```bash
   cd infra
   cdk deploy  # Deploys log-archival-stack
   ```

---

## Verification Checklist

### Day 1
- [ ] New containers running with entrypoint script
- [ ] Logs being written to `/var/log/application/{api,ui}/`
- [ ] CloudWatch log groups receiving logs
- [ ] No errors in application or container logs

### Day 2
- [ ] Logrotate ran (check container logs for execution)
- [ ] `/logs/Archive` contains .gz files
- [ ] CloudWatch still receiving logs (continuous ingestion)

### Day 3
- [ ] S3 bucket exists with exported logs
- [ ] Lambda function executed successfully
- [ ] S3 objects in `cloudwatch-logs/` prefix

### Day 30
- [ ] Oldest logs being deleted per logrotate config
- [ ] `/logs/Archive` doesn't exceed ~3GB (for 100MB/day services)
- [ ] S3 has continuous daily exports

---

## Commands Reference

### Inside Container
```bash
# Check log files exist
ls -lah /var/log/application/api/
ls -lah /logs/Archive/

# Check archive size
du -sh /logs/Archive/

# Verify logrotate config
cat /etc/logrotate.d/api

# Test logrotate (dry run)
logrotate -d -f /etc/logrotate.d/api

# Force rotation immediately
logrotate -f /etc/logrotate.d/api

# Check running processes
ps aux | grep java
ps aux | grep logrotate
```

### AWS CLI
```bash
# Check CloudWatch log group
aws logs describe-log-streams \
  --log-group-name /ecs/uh-groupings/api \
  --order-by LastEventTime

# Get recent logs
aws logs tail /ecs/uh-groupings/api --follow

# Check S3 bucket
aws s3 ls s3://uh-groupings-logs-archive-{account}/

# Check Lambda execution
aws lambda get-function \
  --function-name export-logs-function

# View exports status
aws logs describe-export-tasks
```

---

## Troubleshooting Quick Guide

| Problem | Check | Solution |
|---------|-------|----------|
| Logs not in archive | `ls /logs/Archive/` | Ensure `/logs/Archive` exists and is writable |
| Disk usage high | `du -sh /var/log` | Reduce `rotate` count or `maxage` in logrotate |
| Missing CloudWatch logs | View ECS task def | Add logging driver to task definition |
| S3 export not running | Check Lambda logs | Verify EventBridge rule enabled |
| Rotation not happening | `logrotate -d /etc/logrotate.d/api` | Check config syntax, file patterns |

---

## Configuration Customization

### Change Rotation Frequency
**File:** `logrotate-api.conf`
```conf
# Daily (default)
daily

# Or:
weekly      # Every 7 days
monthly     # Every month
```

### Change Archive Retention
**File:** `logrotate-api.conf`
```conf
rotate 7      # Keep 7 rotations (default)
maxage 30     # Delete files > 30 days (default)

# For longer retention:
rotate 30     # Keep 30 rotations (~30 days)
maxage 60     # Delete after 60 days
```

### Change Log Size Trigger
**File:** `logrotate-api.conf` (add):
```conf
size 50M      # Rotate when file > 50MB
size 500M     # Rotate when file > 500MB
```

### Change Spring Boot Settings
**File:** `logback-spring.xml`
```xml
<maxFileSize>100MB</maxFileSize>        <!-- Trigger rotation -->
<maxHistory>7</maxHistory>              <!-- Keep 7 days -->
<totalSizeCap>1GB</totalSizeCap>        <!-- Cap total size -->
```

### Change Rotation Interval
**File:** `entrypoint.sh`
```bash
sleep 21600   # 6 hours (default)
sleep 3600    # 1 hour
sleep 86400   # 24 hours
```

---

## Cost Optimization Tips

1. **Reduce retention:**
   - Change `maxage 30` → `maxage 14` (save 50%)
   - Reduce S3 lifecycle from 7 years → 2 years

2. **Use compression:**
   - Enable `compress` in logrotate (already done)
   - Savings: 10-20x compression for text logs

3. **Archive to S3 immediately:**
   - Export frequency: 1/day (current) or 1/week
   - Reduces CloudWatch costs by storing in S3 sooner

4. **Monitor costs:**
   ```bash
   aws ce get-cost-and-usage \
     --time-period Start=2026-03-01,End=2026-03-31 \
     --granularity MONTHLY \
     --filter file://filter.json \
     --metrics UnblendedCost
   ```

---

## Monitoring Setup

### CloudWatch Alarms

**High Log Volume:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name api-high-logs \
  --metric-name StorageBytes \
  --namespace AWS/EFS \
  --threshold 1099511627776 \  # 1TB
  --comparison-operator GreaterThanThreshold
```

**Missing Logs:**
```bash
aws cloudwatch put-metric-alarm \
  --alarm-name api-no-logs \
  --metric-name IncomingLogEvents \
  --namespace AWS/Logs \
  --threshold 0 \
  --comparison-operator LessThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --period 1800  # 30 minutes
```

### CloudWatch Dashboard

Create dashboard with:
- EFS storage usage graph
- Log events per hour
- Lambda execution status
- S3 object count

---

## Important Notes

⚠️ **Before Deploying:**
- Ensure EFS is mounted in ECS task definition
- Verify CloudWatch log groups exist
- Test in staging environment first
- Have rollback plan ready

✅ **Post-Deployment:**
- Monitor logs for 48 hours
- Verify rotation happens every 6 hours
- Check S3 exports are occurring daily
- Set up CloudWatch alarms
- Document any custom configurations

📋 **Retention Policy:**
- Local EFS: 30 days (disk space optimization)
- CloudWatch: 7 days (real-time queryable)
- S3: 7 years (compliance & long-term storage)

🔒 **Security:**
- S3 bucket has public access blocked
- Encryption enabled by default
- IAM roles restrict access appropriately

---

## Support Resources

- **Full Documentation:** See `LOG_ROTATION.md`
- **How It Works:** See `IMPLEMENTATION_SUMMARY.md`
- **Deployment Steps:** See `DEPLOYMENT_CHECKLIST.md`
- **Architecture:** See `ARCHITECTURE_DIAGRAMS.md`
- **Configuration Options:** See this Quick Reference

---

## Final Checklist

Before marking as complete:

- [ ] Files copied to service repositories
- [ ] Dockerfiles updated with log rotation configuration
- [ ] Images built and pushed to ECR
- [ ] ECS services updated with new task definitions
- [ ] EFS volumes mounted and accessible
- [ ] CloudWatch log groups created
- [ ] S3 bucket created with lifecycle policies
- [ ] Lambda function deployed for exports
- [ ] Logs appearing in all three tiers
- [ ] CloudWatch alarms configured
- [ ] Team trained on monitoring and troubleshooting
- [ ] Documentation updated with custom parameters

---

**Last Updated:** March 24, 2026  
**Version:** 1.0.0  
**Status:** Ready for Production Deployment

