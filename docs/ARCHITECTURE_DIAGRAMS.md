# Log Rotation Architecture Overview

## High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ECS Task Container                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Application (Spring Boot JAR)                                       │
│           ↓                                                           │
│  Writes to → /var/log/application/api/application.log               │
│                           ↓                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  TIER 1: Container-Level Log Management                      │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  • Spring Boot Logback (optional)                            │  │
│  │  • Rotates when file > 100MB                                 │  │
│  │  • Moves rotated logs to /logs/Archive                       │  │
│  │                                                              │  │
│  │  • Logrotate (background daemon)                             │  │
│  │  • Runs every 6 hours                                        │  │
│  │  • Compresses and archives logs                              │  │
│  │  • Deletes logs > 30 days old                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                           │
│  EFS Volume Mount                                                    │
│  ├── /var/log/application/                                           │
│  │   ├── api/                                                        │
│  │   │   ├── application.log (current)                              │
│  │   │   ├── application.log.1.gz (yesterday)                       │
│  │   │   └── application.log.2.gz (2 days ago)                      │
│  │   └── ui/                                                         │
│  │       ├── application.log (current)                              │
│  │       ├── application.log.1.gz (yesterday)                       │
│  │       └── application.log.2.gz (2 days ago)                      │
│  └── /logs/                                                          │
│      └── Archive/                                                    │
│          ├── application-20260324.1.log.gz (API)                    │
│          ├── application-20260324.2.log.gz (UI)                     │
│          ├── application-20260323.1.log.gz (API)                    │
│          └── application-20260323.2.log.gz (UI)                     │
│                                                                       │
│  Also writes to:                                                     │
│  └── Container STDOUT/STDERR                                        │
└─────────────────────────────────────────────────────────────────────┘
         ↓              ↓              ↓
    ┌────────┐   ┌──────────────┐  ┌───────────────────┐
    │   EFS  │   │ CloudWatch   │  │  Container Log    │
    │ /logs/ │   │ Agent (in    │  │  Collector        │
    │Archive │   │  ECS)        │  │  (built-in)       │
    └────────┘   └──────────────┘  └───────────────────┘
         │              │                    │
         │              ├────────────────────┘
         │              │
         │              ↓
         │      ┌───────────────────────────────────────────┐
         │      │  TIER 2: CloudWatch Logs Aggregation      │
         │      ├───────────────────────────────────────────┤
         │      │  Log Groups:                              │
         │      │  • /ecs/uh-groupings/api                  │
         │      │  • /ecs/uh-groupings/ui                   │
         │      │                                           │
         │      │  Features:                                │
         │      │  • Real-time log streaming                │
         │      │  • 7-day retention                        │
         │      │  • CloudWatch Insights queries            │
         │      │  • Alarms & metrics                       │
         │      │  • Dashboard visualization                │
         │      └───────────────────────────────────────────┘
         │              │
         │              ↓
         │      ┌───────────────────────────────────────────┐
         │      │  Lambda Function (daily at 2 AM UTC)      │
         │      │  Export CloudWatch logs to S3             │
         │      └───────────────────────────────────────────┘
         │              │
         └──────────────┼──────────────────────┐
                        │                      │
                        ↓                      ↓
         ┌──────────────────────────┐  ┌───────────────────────┐
         │  TIER 3: S3 Archive      │  │  Local Archive (EFS)  │
         ├──────────────────────────┤  ├───────────────────────┤
         │  Bucket:                 │  │  Location:            │
         │  uh-groupings-logs-...   │  │  /logs/Archive/       │
         │                          │  │                       │
         │  Prefix:                 │  │  Retention:           │
         │  cloudwatch-logs/        │  │  30 days              │
         │  {service}/              │  │                       │
         │  YYYY/MM/DD/             │  │  Format:              │
         │                          │  │  application-         │
         │  Storage Classes:        │  │  YYYYMMDD.N.log.gz    │
         │  • 0-90 days:            │  │                       │
         │    Standard ($0.023/GB)  │  │  Access:              │
         │  • 90-180 days:          │  │  Direct via EFS       │
         │    Glacier ($0.004/GB)   │  │  (low latency)        │
         │  • 180+ days:            │  │                       │
         │    Deep Archive          │  │  Use Cases:           │
         │    ($0.00099/GB)         │  │  • Quick troubleshoot │
         │  • After 7 years:        │  │  • Hot log analysis   │
         │    Deleted               │  │  • Same-day support   │
         │                          │  │                       │
         │  Features:               │  └───────────────────────┘
         │  • Versioning            │
         │  • Encryption            │
         │  • Access logging        │
         │  • Lifecycle policies    │
         │  • Compliance retention  │
         │                          │
         │  Use Cases:              │
         │  • 7-year compliance     │
         │  • Historical analysis   │
         │  • Long-term audit       │
         │  • Cost-optimized        │
         │    storage               │
         └──────────────────────────┘
```

## Deployment Architecture

```
Source Repositories          AWS Infrastructure              Storage
─────────────────────       ─────────────────────           ───────

uh-groupings-api            EC2/Fargate
├─ app code                 ├─ ECS Cluster
├─ logrotate-api.conf ──→   ├─ ECS Task (API)
├─ entrypoint.sh        │   │  └─ Container
├─ logback-spring.xml   │   │     ├─ Java App
├─ Dockerfile           │   │     ├─ Logrotate daemon
└─ GitHub Actions       │   │     └─ Entrypoint script
   (CI/CD)              │   │
                        │   ├─ ECS Task (API #2)
                        │   ├─ ECS Task (API #3)
                        │   │
uh-groupings-ui         │   ├─ ECS Task (UI)
├─ app code             │   ├─ ECS Task (UI #2)
├─ logrotate-ui.conf ──→   └─ ECS Task (UI #3)
├─ entrypoint.sh        │
├─ logback-spring.xml   │   Shared Storage
├─ Dockerfile           │   ├─ EFS Mount
└─ GitHub Actions       │   │  ├─ /var/log/application/
   (CI/CD)              │   │  └─ /logs/Archive/
                        │   │
                        │   CloudWatch
                        │   ├─ Log Groups
                        │   ├─ Log Streams
                        │   ├─ Insights
                        │   └─ Alarms
                        │
                        └─→ AWS CDK Stack
                            (log-archival-stack.ts)
                            ├─ Lambda function
                            ├─ EventBridge rule
                            ├─ CloudWatch logs
                            ├─ S3 bucket
                            └─ IAM roles

                                        ↓
                            ┌──────────────────────┐
                            │   EFS Storage        │
                            │ (Persistent Logs)    │
                            └──────────────────────┘
                                        ↓
                            ┌──────────────────────┐
                            │  CloudWatch Logs     │
                            │  (7-day hot logs)    │
                            └──────────────────────┘
                                        ↓
                            ┌──────────────────────┐
                            │  S3 Bucket           │
                            │  (7-year archive)    │
                            └──────────────────────┘
```

## Log Retention Timeline

```
Current Date: March 24, 2026

TIER 1: EFS Local Archive
┌─────────────────────────────────────────────────────────────┐
│ Today      |← 7 days →|← 23 days →|   Deleted at 30 days   │
│ Mar 24     |  Mar 18  |  Mar 02   |   Before Feb 23        │
│            |          |          |                          │
│ 🟢 ACTIVE  | 🟡 HOT   | 🟡 WARM  |                          │
│            |          |          |                          │
│ - Fresh    | - Compressed    | - Compressed           │
│ - Expanding| - Searchable    | - Deleted soon         │
│ - In use   | - EFS native    | - In /logs/Archive     │
└─────────────────────────────────────────────────────────────┘
         ↓                     ↓                    ↓
    Real-time         Quick troubleshoot      Older than needed
    monitoring        (same-day issues)       locally


TIER 2: CloudWatch Logs
┌─────────────────────────────────────────────────────────────┐
│ Today      |←─ 7 days retention ─→|   Deleted after 7 days │
│ Mar 24     |  Mar 17 - Mar 24     |   Before Mar 17        │
│            |                      |                        │
│ 🟢 ACTIVE  | 🟡 HOT QUERYABLE    |                        │
│            |                      |                        │
│ - Streaming| - CloudWatch Insights| - No longer accessible │
│ - Monitoring| - Alarms/Metrics    | - Use S3 for older    │
│ - Alarms   | - Dashboard          | - But Lambda exports   │
│ - Dashboards|                      | - Before deletion!     │
└─────────────────────────────────────────────────────────────┘
         ↓                     ↓            (Exported by Lambda)
    Current                Old but            ↓
    production             queryable      Automatic Export


TIER 3: S3 Archive
┌──────────────────────────────────────────────────────────────────┐
│  0-90    │  90-180   │  180-2555  │   After 2555 (7 years)      │
│  days    │   days    │   days     │   Deleted by lifecycle      │
│ Mar-Jun  │ Jun-Dec   │  Dec-2032  │   > March 2033             │
│          │           │            │                            │
│ 🟢 STD   │ 🟡 GLACIER│ 🟠 DEEP   │                            │
│          │           │  ARCHIVE   │                            │
│ $0.023/GB| $0.004/GB | $0.001/GB  │                            │
│          │           │            │  Compliance                │
│ INSTANT  │ 3-5 hrs   │ 12 hrs     │  window                    │
│ retrieval│ retrieval │ retrieval  │  closed                    │
│          │           │            │                            │
│ Hot      │ Compliant | Cost-      │                            │
│ analysis │ retention │ optimized  │                            │
│ and      │           │ long-term  │                            │
│ dashboards          storage      │                            │
└──────────────────────────────────────────────────────────────────┘
    ↓            ↓              ↓              ↓
Regular      Compliance      Long-term      Deleted
queries      archive         backup         (retention
& reports    (safe)          (cheapest)     expired)
```

## Configuration Files Summary

```
File Structure in Docker Image:
───────────────────────────────

/app/
├── app.jar                    (Spring Boot application)
├── entrypoint.sh              (Log rotation scheduler + app launcher)
├── logback-spring.xml         (Spring Boot logback configuration)
└── logback.xml                (Alternative: standard logback)

/etc/
├── logrotate.d/
│   └── api                    (Logrotate configuration for API)
│   │   # Defines rotation schedule
│   │   # Specifies archive location (/logs/Archive)
│   │   # Sets compression and retention
│   └── ui                     (Logrotate configuration for UI)
│       # Same as api, but for UI logs

/var/log/application/
├── api/
│   ├── application.log        (Current log file)
│   ├── application.log.1.gz   (Previous rotation)
│   └── application.log.2.gz   (2 rotations ago)
│
└── ui/
    ├── application.log        (Current log file)
    ├── application.log.1.gz   (Previous rotation)
    └── application.log.2.gz   (2 rotations ago)

/logs/
└── Archive/                   (EFS mounted archive directory)
    ├── application-20260324.1.log.gz  (API logs)
    ├── application-20260324.2.log.gz  (UI logs)
    ├── application-20260323.1.log.gz  (API logs)
    ├── application-20260323.2.log.gz  (UI logs)
    └── ... (up to 30 days)
```

## Monitoring Points

```
Point 1: Container Level
─────────────────────────
├─ Check: /var/log/application/api/ exists
├─ Size:  application.log growing (0-100MB)
├─ Archive: /logs/Archive/ has .gz files
└─ Process: logrotate daemon running (bg)

Point 2: CloudWatch
───────────────────
├─ Log Group: /ecs/uh-groupings/api
├─ Log Streams: task-id/api-container/
├─ Retention: 7 days
├─ Metrics: IncomingLogEvents, IncomingBytes
└─ Query: Use CloudWatch Insights

Point 3: S3 Archive
───────────────────
├─ Bucket: uh-groupings-logs-archive-{acct}
├─ Prefix: cloudwatch-logs/{service}/{date}/
├─ Frequency: Daily export (2 AM UTC)
├─ Objects: Gzipped JSON log files
└─ Lifecycle: Transitions to Glacier → Deep Archive → Delete

Point 4: Disk Usage
──────────────────
├─ EFS Capacity: Monitor total /logs usage
├─ Max per service: ~100MB/day * 30 days = 3GB
├─ Alerts: Trigger if >80% used
└─ Action: Archive to S3 or reduce retention
```

## Cost Estimation (Monthly)

```
Service: API + UI (2 services)
Assuming: 100MB/day logs per service = 200MB/day total

TIER 1: EFS Storage
────────────────────
├─ Usage: 30 days * 200MB = 6GB active
├─ Cost: 6GB * $0.30/GB = $1.80/month
└─ Note: Includes burst throughput

TIER 2: CloudWatch Logs
────────────────────────
├─ Ingestion: 200MB/day * 30 = 6GB
├─ Cost: 6GB * $0.50 = $3.00/month
├─ Retention: 7 days (no storage cost)
└─ Note: Queries and alarms are free

TIER 3: S3 Archive
───────────────────
├─ Daily export: 6GB/month
├─ Storage class breakdown:
│  ├─ 0-90 days: 3GB * $0.023 = $0.069/month
│  ├─ 90-180 days: 3GB * $0.004 = $0.012/month
│  ├─ 180+ days: Minimal cost
├─ Total S3: ~$0.10/month
│
└─ API Calls:
   ├─ CloudWatch export: 60/month (2 per day)
   ├─ S3 list/get: ~$0.05/month
   └─ Total: ~$0.10/month

TOTAL ESTIMATED MONTHLY COST
─────────────────────────────
├─ EFS: $1.80
├─ CloudWatch: $3.00
├─ S3: $0.20
│
└─ TOTAL: ~$5.00/month per service
   (6 services total = ~$30/month)

Note: This assumes 100MB/day. Scale accordingly:
  • 50MB/day services: ~2.50/month
  • 500MB/day services: ~25/month
  • 1GB/day services: ~50/month
```

---

## Next Steps

1. **Review Files:** See `IMPLEMENTATION_SUMMARY.md` for detailed architecture
2. **Deploy:** Follow `DEPLOYMENT_CHECKLIST.md` for step-by-step instructions
3. **Configure:** Customize `LOG_ROTATION.md` for your environment
4. **Monitor:** Set up alarms and dashboards per `monitoring` section
5. **Test:** Validate log rotation in staging before production

