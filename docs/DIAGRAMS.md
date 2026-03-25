# Architecture Diagrams

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ECS Task Container                          │
├─────────────────────────────────────────────────────────────────────┤
│  Application (Spring Boot JAR)                                       │
│           ↓                                                           │
│  Writes to → /var/log/application/api/application.log               │
│                           ↓                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  TIER 1: Container-Level Log Management                      │  │
│  │  • Logrotate daemon (checks every 6 hours)                   │  │
│  │  • Daily rotation with gzip compression                      │  │
│  │  • Moves to /logs/Archive after rotation                     │  │
│  │  • Deletes logs older than 30 days                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                           ↓                                           │
│  EFS Volume Mount → /var/log/application/ & /logs/Archive/          │
│                           ↓                                           │
│  Container STDOUT/STDERR                                            │
└─────────────────────────────────────────────────────────────────────┘
         ↓                                    ↓
    ┌─────────────────┐          ┌─────────────────────────┐
    │  EFS /logs/     │          │  CloudWatch Log         │
    │  Archive/       │          │  Collector              │
    │  (Local logs)   │          │  (streaming)            │
    └─────────────────┘          └─────────────────────────┘
         ↓                                    ↓
    30-day retention                  TIER 2: CloudWatch Logs
                                      ├─ /ecs/uh-groupings/api
                                      ├─ /ecs/uh-groupings/ui
                                      ├─ 7-day retention
                                      ├─ CloudWatch Insights
                                      ├─ Alarms & metrics
                                      └─ Dashboards
                                            ↓
                                      Lambda Export (2 AM UTC)
                                            ↓
         ┌────────────────────────────────────────────────┐
         │     TIER 3: S3 Archive & Lifecycle             │
         ├────────────────────────────────────────────────┤
         │ • 0-90 days: Standard ($0.023/GB)              │
         │ • 90-180 days: Glacier ($0.004/GB)             │
         │ • 180+ days: Deep Archive ($0.001/GB)          │
         │ • After 7 years: Deleted (compliance window)   │
         └────────────────────────────────────────────────┘
```

## Deployment Architecture

```
Source Repositories          AWS Infrastructure              Storage
─────────────────────       ─────────────────────           ───────

uh-groupings-api            ECS Fargate Cluster
├─ Application code         ├─ API Task (with logrotate)
├─ entrypoint.sh            ├─ API Task replica
├─ logrotate-api.conf  ─→   ├─ UI Task (with logrotate)
├─ logback-spring.xml       ├─ UI Task replica
├─ Dockerfile (updated)     │
└─ GitHub Actions           CloudWatch Logs
                            ├─ Log Groups
uh-groupings-ui             ├─ Streams
├─ Application code         └─ Insights
├─ entrypoint.sh
├─ logrotate-ui.conf   ─→   AWS Lambda
├─ logback-spring.xml       ├─ Export function
├─ Dockerfile (updated)     └─ Daily trigger
└─ GitHub Actions
                            EventBridge
AWS CDK Stack               └─ Scheduled rule (2 AM UTC)
├─ log-archival-stack.ts
├─ S3 bucket config     ─→   S3 Bucket ←─────────────┐
├─ Lambda function          ├─ cloudwatch-logs/      │
├─ CloudWatch groups        ├─ {service}/{date}      │
└─ IAM roles                └─ Lifecycle policies    │
                                                     │
                            EFS Mount                │
                            ├─ /var/log/application/ │
                            └─ /logs/Archive/  ──────┘
```

## Log Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Application Output                                     │
│  ├─ application.log (current, 0-100MB)                │
│  ├─ STDOUT/STDERR (container logs)                     │
│  └─ Structured logging via Spring Boot                 │
└─────────────────────────────────────────────────────────┘
         │                                │
         ├─ Logrotate Check (every 6h)    │
         │        │                       │
         │        ├─ Triggers rotation?   │
         │        │    (daily or 100MB)   │
         │        │                       │
         │        ↓                       │
         │   ┌─────────────────────┐      │
         │   │ Compress & Archive  │      │
         │   │ application.log.gz  │      │
         │   │ → /logs/Archive/    │      │
         │   └─────────────────────┘      │
         │                                 │
         ├─ Fresh log file created        ├─ Streams to CloudWatch
         │  application.log (new)         │
         │                                 ↓
         ↓                          ┌────────────────────┐
    EFS Storage                     │ CloudWatch Logs    │
    ├─ /var/log/application/        │ Log Groups:        │
    │  ├─ api/                      │ • /ecs/uh-groupings/api
    │  │  └─ application.log        │ • /ecs/uh-groupings/ui
    │  └─ ui/                       │                    │
    │     └─ application.log        │ Features:          │
    │                               │ • Real-time        │
    └─ /logs/Archive/               │ • 7-day retention  │
       ├─ app-20260324.1.log.gz     │ • Queryable        │
       ├─ app-20260323.1.log.gz     └────────────────────┘
       └─ ... (up to 30 days)              │
                                          │ Lambda Export
                                          │ (daily @ 2 AM)
                                          ↓
                                    ┌────────────────────┐
                                    │ S3 Bucket          │
                                    │ • 7-year retention │
                                    │ • Cost optimized   │
                                    │ • Lifecycle rules  │
                                    └────────────────────┘
```

## Log Retention Timeline

```
Current Date: March 24, 2026

TIER 1: EFS Local Archive (30 days)
┌──────────────────────────────────────────────────────┐
│ Today    │ 7 days   │ 23 days  │ Deleted at day 30  │
│ Mar 24   │ Mar 18   │ Mar 02   │ Before Feb 23      │
│          │          │          │                    │
│ 🟢 ACTIVE│ 🟡 HOT   │ 🟡 WARM  │                    │
│ Fresh    │ Compressed
│ Expanding│ Searchable│ Compressed    │ Deleted       │
└──────────────────────────────────────────────────────┘

TIER 2: CloudWatch Logs (7 days)
┌──────────────────────────────────────────────────────┐
│ Today    │ ← 7 days retention → │ Deleted after 7d   │
│ Mar 24   │ Mar 17 - Mar 24      │ Before Mar 17      │
│          │                      │                    │
│ 🟢 ACTIVE│ 🟡 HOT & QUERYABLE   │                    │
│ Streaming│ Insights/Alarms/     │ Exported to S3     │
│ Real-time│ Dashboards           │ before deletion    │
└──────────────────────────────────────────────────────┘

TIER 3: S3 Archive (7 years with transitions)
┌────────────────────────────────────────────────────────┐
│ 0-90d   │ 90-180d  │ 180-2555d │ After 2555d (7y)   │
│ Mar-Jun │ Jun-Dec  │ Dec-2032  │ > March 2033       │
│         │          │           │                    │
│ 🟢 STD  │ 🟡 GLACIER│ 🟠 DEEP  │ ❌ DELETED         │
│ $0.023  │ $0.004   │ $0.001   │ (compliance end)   │
│ /GB/mo  │ /GB/mo   │ /GB/mo   │                    │
│         │          │           │                    │
│ INSTANT │ 3-5 hrs  │ 12 hrs    │                    │
│ retrieval│ retrieval│ retrieval │                    │
└────────────────────────────────────────────────────────┘
```

## Container-to-Cloud Data Flow

```
                    ECS Task Container
                    ┌────────────────────────────────────┐
                    │  Application                       │
                    │  (Spring Boot - Java 17)           │
                    └────────────────────────────────────┘
                                ↓
                    ┌────────────────────────────────────┐
                    │  Logging                           │
                    │  ├─ Spring Boot Logback (optional) │
                    │  ├─ Logrotate daemon (background)  │
                    │  └─ STDOUT/STDERR (container logs) │
                    └────────────────────────────────────┘
                                ↓
                    ┌────────────────────────────────────┐
                    │  File System                       │
                    │  ├─ /var/log/application/{service}/
                    │  │   └─ application.log (current)  │
                    │  └─ /logs/Archive/                 │
                    │      └─ *.log.gz (rotated)         │
                    └────────────────────────────────────┘
                        │                │
                        ↓                ↓
            ┌──────────────────┐  ┌──────────────────┐
            │  EFS Storage     │  │  CloudWatch      │
            │  (Persistent)    │  │  (Streaming)     │
            └──────────────────┘  └──────────────────┘
                   ↓ (30 days)             ↓ (7 days)
            ┌──────────────────┐  ┌──────────────────┐
            │  /logs/Archive/  │  │  Log Insights    │
            │  (Queryable)     │  │  (Searchable)    │
            └──────────────────┘  └──────────────────┘
                                         ↓
                                  Lambda Export
                                  (2 AM UTC daily)
                                         ↓
                                  ┌──────────────────┐
                                  │  S3 Bucket       │
                                  │  (7-year)        │
                                  └──────────────────┘
                                    ↓ Lifecycle
                                  ┌──────────────────┐
                                  │  Glacier/        │
                                  │  Deep Archive    │
                                  └──────────────────┘
```

## Cost Breakdown (100MB/day per service)

```
┌─────────────────────────────────────────────────────┐
│  Monthly Cost Estimation (2 services, 200MB/day)   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TIER 1: EFS Storage                                │
│  ├─ 6GB × $0.30/GB = $1.80/month                   │
│  └─ Includes: Storage + burst throughput           │
│                                                     │
│  TIER 2: CloudWatch Logs                            │
│  ├─ 6GB × $0.50/GB = $3.00/month                   │
│  ├─ 7-day retention (no extra charge)              │
│  └─ Queries/alarms included                        │
│                                                     │
│  TIER 3: S3 Storage & Exports                       │
│  ├─ 6GB/month exports                              │
│  ├─ Standard (0-90d): 3GB × $0.023 = $0.07        │
│  ├─ Glacier (90-180d): 3GB × $0.004 = $0.01       │
│  ├─ Lambda invocations: ~$0.05/month               │
│  └─ Total S3: ~$0.20/month                         │
│                                                     │
├─────────────────────────────────────────────────────┤
│  TOTAL: ~$5.00/month per service pair               │
│  (Scales linearly with log volume)                  │
└─────────────────────────────────────────────────────┘

Example Scaling:
  • 50MB/day: $2.50/month
  • 100MB/day: $5.00/month
  • 500MB/day: $25.00/month
  • 1GB/day: $50.00/month
```

