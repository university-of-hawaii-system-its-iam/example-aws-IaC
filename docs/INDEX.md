# Documentation Index

Welcome to the log rotation implementation documentation. Choose your starting point based on your role.

## 🎯 Quick Navigation

### **For Architects/Leads:**
1. **Start:** [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) - Visual overview
2. **Then:** [`IMPLEMENTATION_SUMMARY.md`](./IMPLEMENTATION_SUMMARY.md) - Complete explanation
3. **Finally:** [`DEPLOYMENT_CHECKLIST.md`](./DEPLOYMENT_CHECKLIST.md) - Rollout plan

### **For DevOps/Infrastructure Engineers:**
1. **Start:** [`QUICK_REFERENCE.md`](./QUICK_REFERENCE.md) - Quick lookup
2. **Then:** [`DEPLOYMENT_CHECKLIST.md`](./DEPLOYMENT_CHECKLIST.md) - Step-by-step guide
3. **Reference:** [`LOG_ROTATION.md`](./LOG_ROTATION.md) - Detailed configurations

### **For Application Developers:**
1. **Start:** [`README_LOG_ROTATION.md`](./README_LOG_ROTATION.md) - Quick start
2. **Reference:** [`QUICK_REFERENCE.md`](./QUICK_REFERENCE.md) - Configuration options
3. **Details:** [`LOG_ROTATION.md`](./LOG_ROTATION.md) - Spring Boot logging

### **For Support/Operations:**
1. **Start:** [`QUICK_REFERENCE.md`](./QUICK_REFERENCE.md) - Verification & troubleshooting
2. **Then:** [`DEPLOYMENT_CHECKLIST.md`](./DEPLOYMENT_CHECKLIST.md) - Monitoring section
3. **Reference:** All docs for context when issues arise

---

## 📁 File Descriptions

| File | Purpose | Audience | Length |
|------|---------|----------|--------|
| [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) | Visual flows, deployment architecture, cost estimation | Architects, leaders | Medium |
| [`IMPLEMENTATION_SUMMARY.md`](./IMPLEMENTATION_SUMMARY.md) | Complete how-it-works, step-by-step explanation | Everyone | Long |
| [`DEPLOYMENT_CHECKLIST.md`](./DEPLOYMENT_CHECKLIST.md) | Detailed deployment steps with commands | DevOps, infrastructure | Long |
| [`QUICK_REFERENCE.md`](./QUICK_REFERENCE.md) | Quick lookup, commands, troubleshooting | Operations, developers | Medium |
| [`LOG_ROTATION.md`](./LOG_ROTATION.md) | Comprehensive configuration guide | Advanced users | Very Long |
| [`README_LOG_ROTATION.md`](./README_LOG_ROTATION.md) | Quick start guide | New team members | Short |

---

## 🚀 What Was Implemented

A **three-tier log management system:**

1. **TIER 1: Container-Level Rotation (EFS)**
   - Daily rotation with compression
   - Moves old logs to `/logs/Archive`
   - 30-day retention
   - Managed by logrotate daemon

2. **TIER 2: Real-Time Aggregation (CloudWatch)**
   - Immediate log streaming to CloudWatch
   - 7-day queryable retention
   - CloudWatch Insights, alarms, metrics
   - Used for monitoring and debugging

3. **TIER 3: Long-Term Archive (S3)**
   - Daily Lambda exports from CloudWatch
   - 7-year retention for compliance
   - Cost-optimized storage classes
   - Lifecycle: Standard → Glacier → Deep Archive

---

## 📋 At a Glance

### **Files You Need to Use**

**Container Configuration** (copy to service repositories):
- `entrypoint.sh` - Startup script with logrotate scheduling
- `logrotate-*.conf` - Rotation rules (daily, archive to /logs/Archive)
- `logback-spring.xml` - Spring Boot logging (optional)
- Updated `Dockerfile` - Includes logrotate and log directories

**Infrastructure** (AWS CDK):
- `log-archival-stack.ts` - CloudWatch logs export to S3

### **Key Metrics**

- **Rotation Frequency:** Daily
- **Size Trigger:** 100MB
- **Compression:** gzip
- **Local Retention:** 7 days on disk, max 30 days
- **CloudWatch Retention:** 7 days
- **S3 Retention:** 7 years
- **Archive Location:** `/logs/Archive`

### **Cost Estimate**

For 2 services with 100MB/day logs each:
- EFS: $1.80/month
- CloudWatch: $3.00/month
- S3: $0.20/month
- **Total: ~$5/month**

---

## ✅ Quick Verification

After deployment, you should see:

**Day 1:**
- [ ] Logs in `/var/log/application/{api,ui}/`
- [ ] CloudWatch log groups receiving logs
- [ ] No permission errors

**Day 2:**
- [ ] Logrotate executed (check container logs)
- [ ] `/logs/Archive` has .gz files
- [ ] CloudWatch still aggregating

**Day 3:**
- [ ] S3 bucket exists with exported logs
- [ ] Lambda function executed successfully

---

## 🔧 Common Configuration Changes

### **Change Rotation Frequency**
```conf
# In logrotate-api.conf
daily    → weekly    (every 7 days)
daily    → monthly   (every month)
```

### **Change Retention**
```conf
rotate 7      → rotate 30   (keep more versions)
maxage 30     → maxage 14   (delete sooner)
```

### **Change Log Size Trigger**
```conf
size 100M     → size 50M    (rotate sooner)
size 100M     → size 500M   (rotate later)
```

---

## 🆘 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| Logs not rotating | Check: `logrotate -d /etc/logrotate.d/api` |
| High disk usage | Reduce `rotate` count or `maxage` value |
| Missing CloudWatch | Add logging driver to ECS task definition |
| S3 export failing | Check Lambda logs and IAM permissions |

---

## 📞 Need Help?

- **"How does this work?"** → [`IMPLEMENTATION_SUMMARY.md`](./IMPLEMENTATION_SUMMARY.md)
- **"How do I deploy?"** → [`DEPLOYMENT_CHECKLIST.md`](./DEPLOYMENT_CHECKLIST.md)
- **"How do I configure X?"** → [`LOG_ROTATION.md`](./LOG_ROTATION.md)
- **"How do I troubleshoot?"** → [`QUICK_REFERENCE.md`](./QUICK_REFERENCE.md)
- **"Show me the architecture"** → [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md)
- **"Quick start?"** → [`README_LOG_ROTATION.md`](./README_LOG_ROTATION.md)

---

## 🎯 Next Steps

1. **Choose** a starting document from above based on your role
2. **Review** the architecture and how it works
3. **Follow** the deployment checklist
4. **Verify** logs are rotating in all three tiers
5. **Monitor** and set up alarms

---

**Status:** ✅ Complete and Ready for Production Deployment

**Last Updated:** March 24, 2026


