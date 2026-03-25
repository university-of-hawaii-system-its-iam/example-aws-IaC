# Log Rotation Implementation Summary

This repository now includes comprehensive log rotation and archival for ECS services running on AWS Fargate.

## 📖 Documentation

All detailed documentation is located in the `docs/` folder. Start here based on your role:

### Quick Links
- **For Architects/Leads:** [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md)
- **For DevOps/Infrastructure:** [`docs/DEPLOYMENT_CHECKLIST.md`](docs/DEPLOYMENT_CHECKLIST.md)
- **For Developers:** [`docs/README_LOG_ROTATION.md`](docs/README_LOG_ROTATION.md)
- **For Support/Operations:** [`docs/QUICK_REFERENCE.md`](docs/QUICK_REFERENCE.md)
- **Full Index:** [`docs/INDEX.md`](docs/INDEX.md)

## 🎯 What Was Implemented

A three-tier log management system:

**TIER 1: Container-Level Rotation (EFS)**
- Daily rotation with automatic compression
- Old logs moved to `/logs/Archive`
- 30-day retention locally
- Managed by logrotate daemon running in container

**TIER 2: Real-Time Aggregation (CloudWatch)**
- Immediate log streaming from ECS tasks
- 7-day retention for querying
- CloudWatch Insights, alarms, and metrics
- Used for monitoring and debugging

**TIER 3: Long-Term Archive (S3)**
- Daily Lambda exports from CloudWatch to S3
- 7-year retention for compliance
- Cost-optimized (Standard → Glacier → Deep Archive)
- Lifecycle policies for automated transitions

## 📁 Files Created/Modified

### Container Configuration (in service repositories)

**For each service (`uh-groupings-api` and `uh-groupings-ui`):**
- ✅ `entrypoint.sh` - Startup script with logrotate scheduling
- ✅ `logrotate-*.conf` - Rotation rules and configuration
- ✅ `logback-spring.xml` - Spring Boot logging (optional)
- ✅ `Dockerfile` - Updated with logrotate and log directories

### Infrastructure (AWS CDK)

- ✅ `infra/lib/log-archival-stack.ts` - Complete CDK stack for S3, CloudWatch, Lambda, and EventBridge

### Documentation (in `docs/` folder)

- ✅ `docs/LOG_ROTATION.md` - Comprehensive configuration guide
- ✅ `docs/IMPLEMENTATION_SUMMARY.md` - Complete how-it-works guide
- ✅ `docs/DEPLOYMENT_CHECKLIST.md` - Step-by-step deployment
- ✅ `docs/QUICK_REFERENCE.md` - Quick lookup and troubleshooting
- ✅ `docs/ARCHITECTURE_DIAGRAMS.md` - Visual architecture and flows
- ✅ `docs/README_LOG_ROTATION.md` - Quick start guide
- ✅ `docs/INDEX.md` - Documentation index

## 🚀 Quick Start

1. **Review the architecture:**
   ```bash
   cat docs/ARCHITECTURE_DIAGRAMS.md
   ```

2. **Copy container files to service repositories:**
   - `services/api/entrypoint.sh`
   - `services/api/logrotate-api.conf`
   - `services/api/logback-spring.xml`
   - `services/ui/entrypoint.sh`
   - `services/ui/logrotate-ui.conf`
   - `services/ui/logback-spring.xml`

3. **Follow the deployment checklist:**
   ```bash
   cat docs/DEPLOYMENT_CHECKLIST.md
   ```

## 💾 Storage & Cost

- **EFS (30 days):** $1.80/month (local archive)
- **CloudWatch (7 days):** $3.00/month (real-time queries)
- **S3 (7 years):** $0.20/month (long-term archive)
- **Total:** ~$5/month per service pair

*(Assuming 100MB/day logs per service)*

## ✅ Verification

After deployment, verify across all three tiers:

```bash
# TIER 1: Check local archive
ls -la /logs/Archive/

# TIER 2: Check CloudWatch
aws logs tail /ecs/uh-groupings/api --follow

# TIER 3: Check S3
aws s3 ls s3://uh-groupings-logs-archive-{account-id}/
```

## 📋 Implementation Details

### Rotation Schedule
- **Frequency:** Daily (checked every 6 hours)
- **Size Trigger:** 100MB
- **Compression:** gzip (automatic)
- **Retention:** 7 days on disk, 30 days max
- **Archive:** `/logs/Archive/`

### File Naming
```
Current:  /var/log/application/api/application.log
Rotated:  /var/log/application/api/application.log.1.gz
Archived: /logs/Archive/application-20260324.1.log.gz
S3:       s3://bucket/cloudwatch-logs/api/2026/03/24/
```

## 🔧 Configuration

All configuration files include inline comments. Common customizations:

**Change rotation frequency:**
```conf
# In logrotate-api.conf
daily    # Change to: weekly, monthly
```

**Change retention:**
```conf
rotate 7      # Keep 7 rotations
maxage 30     # Delete after 30 days
```

**Change log size trigger:**
```conf
size 100M     # Rotate when file exceeds 100MB
```

For more options, see `docs/LOG_ROTATION.md`.

## 🆘 Support

- **Architecture questions?** → See `docs/ARCHITECTURE_DIAGRAMS.md`
- **How to deploy?** → See `docs/DEPLOYMENT_CHECKLIST.md`
- **Configuration help?** → See `docs/LOG_ROTATION.md`
- **Troubleshooting?** → See `docs/QUICK_REFERENCE.md`
- **New to this?** → See `docs/README_LOG_ROTATION.md`
- **Need index?** → See `docs/INDEX.md`

## 📚 Complete Documentation

All comprehensive documentation is in the `docs/` folder:

```
docs/
├── INDEX.md                      ← Start here!
├── ARCHITECTURE_DIAGRAMS.md      ← Visual overview
├── IMPLEMENTATION_SUMMARY.md     ← How it works
├── DEPLOYMENT_CHECKLIST.md       ← Step-by-step
├── QUICK_REFERENCE.md            ← Lookup & troubleshooting
├── LOG_ROTATION.md               ← Detailed configs
└── README_LOG_ROTATION.md        ← Quick start
```

## ✨ Key Features

✅ **Automatic Daily Rotation** - No manual intervention
✅ **Three-Tier Retention** - Hot, warm, and cold storage
✅ **Zero App Changes** - Works with existing applications
✅ **Production Ready** - Multi-AZ, lifecycle policies, monitoring
✅ **Cost Optimized** - ~$5/month for typical services
✅ **Easy to Monitor** - CloudWatch Insights, alarms, dashboards

## 📝 Status

**Status:** ✅ Complete and Ready for Production Deployment

**Version:** 1.0.0

**Last Updated:** March 24, 2026

## 🎯 Next Steps

1. Review [`docs/INDEX.md`](docs/INDEX.md) for documentation index
2. Choose a starting point based on your role
3. Follow the deployment checklist
4. Verify logs in all three tiers
5. Set up monitoring and alarms

---

**For detailed information, start with [`docs/INDEX.md`](docs/INDEX.md)**

