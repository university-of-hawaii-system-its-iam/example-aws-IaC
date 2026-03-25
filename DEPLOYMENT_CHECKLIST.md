# Log Rotation Deployment Checklist

This checklist guides you through deploying log rotation in your production environment.

## Pre-Deployment Planning

- [ ] Review `IMPLEMENTATION_SUMMARY.md` for architecture overview
- [ ] Review `docs/LOG_ROTATION.md` for detailed configuration options
- [ ] Determine your log retention policy (default: 30 days on EFS, 7 years in S3)
- [ ] Estimate disk space needs (100MB/day per service = ~3GB/month)
- [ ] Plan S3 bucket naming (must be globally unique)
- [ ] Schedule deployment for low-traffic period
- [ ] Prepare rollback plan

## Phase 1: Prepare Service Repositories

### Update `uh-groupings-api` Repository

- [ ] Copy files from this repository:
  - [ ] `services/api/entrypoint.sh` → repository root or build context
  - [ ] `services/api/logrotate-api.conf` → repository root or build context
  - [ ] `services/api/logback-spring.xml` → `src/main/resources/`

- [ ] Update your `Dockerfile`:
  ```dockerfile
  # Add after the runtime stage starts
  RUN apk add --no-cache logrotate
  
  # Create directories
  RUN mkdir -p /var/log/application/api /logs/Archive && \
      chmod 755 /var/log/application/api /logs/Archive
  
  # Copy configuration files
  COPY entrypoint.sh /app/entrypoint.sh
  COPY logrotate-api.conf /etc/logrotate.d/api
  COPY logback-spring.xml /app/logback-spring.xml
  RUN chmod +x /app/entrypoint.sh
  
  # Change CMD to ENTRYPOINT
  ENTRYPOINT ["/app/entrypoint.sh"]
  ```

- [ ] Update `application.properties` (optional):
  ```properties
  logging.config=classpath:logback-spring.xml
  logging.file.name=/var/log/application/api/application.log
  ```

- [ ] Build and test Docker image locally:
  ```bash
  docker build -t uh-groupings-api:test .
  docker run --rm -v /tmp/logs:/logs uh-groupings-api:test
  # Test: Check /tmp/logs/Archive after 6+ hours (adjust entrypoint.sh for testing)
  ```

- [ ] Commit and push changes to GitHub

### Update `uh-groupings-ui` Repository

- [ ] Copy files:
  - [ ] `services/ui/entrypoint.sh`
  - [ ] `services/ui/logrotate-ui.conf`
  - [ ] `services/ui/logback-spring.xml` → `src/main/resources/`

- [ ] Update `Dockerfile` (same as API, but with `logrotate-ui.conf`)

- [ ] Update `application.properties` (optional)

- [ ] Build and test locally

- [ ] Commit and push to GitHub

## Phase 2: Infrastructure Updates

### Create S3 Bucket and CloudWatch Setup

- [ ] Add `log-archival-stack.ts` to `infra/lib/`:
  ```bash
  cp infra/lib/log-archival-stack.ts /your/infra/repo/lib/
  ```

- [ ] Update `infra/bin/app.ts` to include LogArchivalStack:
  ```typescript
  import { LogArchivalStack } from '../lib/log-archival-stack';
  
  // In app initialization
  new LogArchivalStack(app, 'uh-groupings-log-archival');
  ```

- [ ] Validate CDK:
  ```bash
  cd infra
  npm install
  cdk synth
  ```

- [ ] Test deployment in non-prod environment first:
  ```bash
  cdk deploy --context environment=staging
  ```

- [ ] After validation, deploy to production:
  ```bash
  cdk deploy --context environment=prod
  ```

- [ ] Verify stack creation:
  ```bash
  aws cloudformation describe-stacks --stack-name uh-groupings-log-archival
  aws s3 ls | grep uh-groupings-logs-archive
  aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `uh-groupings`)]'
  ```

## Phase 3: ECS Configuration

### Update Task Definition

- [ ] Identify ECS Cluster name
- [ ] Get current task definition:
  ```bash
  aws ecs describe-task-definition \
    --task-definition uh-groupings-api:latest \
    --query 'taskDefinition' > api-task-def.json
  ```

- [ ] Add EFS volume mount (if not already configured):
  ```json
  {
    "name": "logs-volume",
    "efsVolumeConfiguration": {
      "fileSystemId": "fs-xxxxxxxx",
      "transitEncryption": "ENABLED",
      "authorizationConfig": {
        "accessPointId": "fsap-xxxxxxxx"
      }
    }
  }
  ```

- [ ] Add mount points to container:
  ```json
  {
    "sourceVolume": "logs-volume",
    "containerPath": "/var/log/application",
    "readOnly": false
  },
  {
    "sourceVolume": "logs-volume",
    "containerPath": "/logs",
    "readOnly": false
  }
  ```

- [ ] Add logging driver (if not present):
  ```json
  {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/uh-groupings/api",
      "awslogs-region": "us-east-1",
      "awslogs-stream-prefix": "api-task"
    }
  }
  ```

- [ ] Register new task definition:
  ```bash
  aws ecs register-task-definition \
    --cli-input-json file://api-task-def.json
  ```

- [ ] Update ECS service:
  ```bash
  aws ecs update-service \
    --cluster uh-groupings-cluster \
    --service uh-groupings-api \
    --task-definition uh-groupings-api:latest \
    --force-new-deployment
  ```

- [ ] Repeat for UI service

## Phase 4: ECR Image Updates

### Trigger New Builds

- [ ] Push changes to GitHub in `uh-groupings-api` repository
  - [ ] Create new git tag: `v1.x.x-with-log-rotation`
  - [ ] GitHub Actions should trigger
  - [ ] Monitor build progress in GitHub Actions

- [ ] Verify image pushed to ECR:
  ```bash
  aws ecr describe-images \
    --repository-name uh-groupings-api \
    --query 'imageDetails[-1]'
  ```

- [ ] Repeat for `uh-groupings-ui` repository

### Verify Image Configuration

- [ ] Pull image locally and inspect:
  ```bash
  docker pull 123456789.dkr.ecr.us-east-1.amazonaws.com/uh-groupings-api:latest
  docker inspect <image-id> | grep -A 20 "Entrypoint\|Cmd"
  ```

- [ ] Verify files are present:
  ```bash
  docker run --entrypoint ls <image-id> /etc/logrotate.d/
  docker run --entrypoint cat <image-id> /app/entrypoint.sh
  ```

## Phase 5: Deployment and Testing

### Update ECS Services

- [ ] Update ECS service task definition to use new image:
  ```bash
  aws ecs update-service \
    --cluster uh-groupings-cluster \
    --service uh-groupings-api \
    --task-definition uh-groupings-api:latest \
    --force-new-deployment
  ```

- [ ] Monitor deployment:
  ```bash
  aws ecs describe-services \
    --cluster uh-groupings-cluster \
    --services uh-groupings-api \
    --query 'services[0].deployments'
  ```

- [ ] Wait for new tasks to reach RUNNING status
- [ ] Repeat for UI service

### Verify Logs Are Being Written

- [ ] Check CloudWatch log group:
  ```bash
  aws logs describe-log-streams \
    --log-group-name /ecs/uh-groupings/api \
    --order-by LastEventTime \
    --descending
  ```

- [ ] Check EFS for log files (via EC2 bastion or ECS Exec):
  ```bash
  aws ecs execute-command \
    --cluster uh-groupings-cluster \
    --task <task-id> \
    --container uh-groupings-api \
    --interactive \
    --command "/bin/sh"
  
  # Inside container
  ls -la /var/log/application/api/
  ```

- [ ] Verify application is running normally:
  - [ ] Health checks passing
  - [ ] No errors in CloudWatch logs
  - [ ] Application endpoints responding

## Phase 6: Monitor Log Rotation

### Initial Validation (First 6-24 Hours)

- [ ] Check that logs are being created:
  ```bash
  # In container
  ls -lah /var/log/application/api/
  ```

- [ ] Check entrypoint script execution:
  ```bash
  # In container
  ps aux | grep java
  ps aux | grep logrotate
  ```

- [ ] Verify no errors in application logs:
  ```bash
  aws logs tail /ecs/uh-groupings/api --follow
  ```

### Schedule Verification (Post-Deployment)

- [ ] **Day 1:** Verify logs are being written
  - [ ] Check `/var/log/application/api/application.log` size
  - [ ] Verify no permission errors

- [ ] **Day 2:** Verify first rotation check runs
  - [ ] Logrotate runs every 6 hours
  - [ ] No errors in CloudWatch

- [ ] **Day 8:** Verify archive directory has rotated logs
  - [ ] `/logs/Archive/` should have compressed logs
  - [ ] Files should be 30+ days old before deletion

- [ ] **Day 2 @ 2 AM:** Verify CloudWatch export to S3
  - [ ] Lambda function execution logged
  - [ ] S3 bucket has exported logs
  - [ ] Check: `aws s3 ls s3://uh-groupings-logs-archive-{account}/`

## Phase 7: Monitoring and Alarms

### Setup CloudWatch Alarms

- [ ] Create alarm for high log volume:
  ```bash
  aws cloudwatch put-metric-alarm \
    --alarm-name uh-groupings-api-high-log-volume \
    --alarm-description "Alert when API logs exceed 1GB" \
    --metric-name StorageBytes \
    --namespace AWS/EFS \
    --statistic Average \
    --period 3600 \
    --evaluation-periods 1 \
    --threshold 1099511627776 \
    --comparison-operator GreaterThanThreshold
  ```

- [ ] Create alarm for missing logs:
  ```bash
  aws cloudwatch put-metric-alarm \
    --alarm-name uh-groupings-api-no-logs \
    --alarm-description "Alert when no logs for 30 minutes" \
    --metric-name IncomingLogEvents \
    --namespace AWS/Logs \
    --log-group-name /ecs/uh-groupings/api \
    --statistic Sum \
    --period 1800 \
    --evaluation-periods 1 \
    --threshold 0 \
    --comparison-operator LessThanOrEqualToThreshold
  ```

- [ ] Create alarm for Lambda export failures:
  ```bash
  aws cloudwatch put-metric-alarm \
    --alarm-name uh-groupings-log-export-failed \
    --alarm-description "Alert when log export fails" \
    --metric-name Errors \
    --namespace AWS/Lambda \
    --dimensions Name=FunctionName,Value=export-logs-function \
    --statistic Sum \
    --period 3600 \
    --evaluation-periods 1 \
    --threshold 0 \
    --comparison-operator GreaterThanThreshold
  ```

### Setup Dashboard

- [ ] Create CloudWatch dashboard with:
  - [ ] EFS storage usage graph
  - [ ] CloudWatch log event count
  - [ ] Lambda execution history
  - [ ] Error rate metric

## Troubleshooting

### Issue: Logs not appearing in `/logs/Archive`

**Check:**
```bash
# In container
logrotate -d -f /etc/logrotate.d/api  # Dry run
ps aux | grep entrypoint
ls -la /var/log/application/api/
```

**Solution:**
- Verify log files exist and match pattern: `/var/log/application/api/*.log`
- Check permissions on `/logs/Archive`: `chmod 755 /logs/Archive`
- Increase log verbosity: Update sleep time in entrypoint.sh for testing

### Issue: High disk usage

**Check:**
```bash
du -sh /var/log/application/*
du -sh /logs/Archive/
df -h
```

**Solution:**
- Reduce `rotate` count in logrotate config
- Reduce `maxage` value
- Enable compression verification: `gunzip -t /logs/Archive/*.gz`

### Issue: CloudWatch logs empty

**Check:**
```bash
aws logs describe-log-streams --log-group-name /ecs/uh-groupings/api
aws logs get-log-events --log-group-name /ecs/uh-groupings/api \
  --log-stream-name <stream-name>
```

**Solution:**
- Verify task definition has logging driver configured
- Check ECS task execution role has CloudWatch permissions
- Verify `awslogs` configuration is correct in task definition

### Issue: S3 export not running

**Check:**
```bash
aws lambda get-function --function-name export-logs-function
aws cloudwatch get-metric-statistics --namespace AWS/Lambda \
  --metric-name Invocations --start-time 2026-03-23T00:00:00Z \
  --end-time 2026-03-24T00:00:00Z --period 3600 --statistics Sum
```

**Solution:**
- Verify EventBridge rule is enabled
- Check Lambda execution role has CloudWatch Logs permissions
- Verify S3 bucket name is correct in Lambda environment

## Rollback Plan

If issues occur, you can rollback:

1. **Revert ECS Service:**
   ```bash
   aws ecs update-service \
     --cluster uh-groupings-cluster \
     --service uh-groupings-api \
     --task-definition uh-groupings-api:previous-version \
     --force-new-deployment
   ```

2. **Check previous image:**
   ```bash
   aws ecr describe-image-detail --repository-name uh-groupings-api
   ```

3. **Delete infrastructure (if needed):**
   ```bash
   cdk destroy --force
   ```

## Sign-Off

- [ ] All validations passed
- [ ] Logs rotating correctly
- [ ] CloudWatch ingesting logs
- [ ] S3 receiving exports
- [ ] Alarms configured
- [ ] Team notified
- [ ] Documentation updated

---

## Support Resources

- **General Questions:** See `IMPLEMENTATION_SUMMARY.md`
- **Configuration Details:** See `docs/LOG_ROTATION.md`
- **Quick Start:** See `README_LOG_ROTATION.md`
- **AWS Docs:** https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_cloudwatch_logs.html


