# Updated Project Structure

## Repository Organization

```
example-aws-iac/                    # THIS REPOSITORY
├── .github/workflows/
│   ├── deploy-dev.yml              # Deploy to development
│   └── deploy-prod.yml             # Deploy to production
│
├── infra/                           # AWS CDK Infrastructure (Python)
│   ├── app.py                      # CDK app entry point
│   ├── stacks/
│   │   ├── __init__.py
│   │   ├── network_stack.py         # VPC, subnets, security
│   │   ├── app_stack.py             # ECS, services, ALB
│   │   │   └── References:
│   │   │       - uh-groupings-api:release-prod (from ECR)
│   │   │       - uh-groupings-ui:release-prod (from ECR)
│   │   ├── data_stack.py            # RDS, cache, secrets
│   │   └── log_archival_stack.py    # S3, CloudWatch, Lambda for log archival
│   ├── cdk.json
│   ├── requirements.txt
│   └── setup.py
│
├── services/                        # REFERENCE DOCUMENTATION ONLY
│   ├── api/
│   │   ├── README.md                # Links to uh-groupings-api repo
│   │   └── Dockerfile               # Example Dockerfile structure
│   │
│   └── ui/
│       ├── README.md                # Links to uh-groupings-ui repo
│       └── Dockerfile               # Example Dockerfile structure
│
├── docs/
│   └── architecture/
│       ├── README.md                # Comprehensive architecture docs
│       └── MULTI_REPO_ARCHITECTURE.md  # (to be created)
│
└── README.md                        # Main project documentation
                                    # References both external repos
```

## External Repositories

```
uh-groupings-api/                   # EXTERNAL REPOSITORY
├── src/                             # Java/Node.js source code
├── Dockerfile                       # Builds container image
├── package.json / pom.xml           # Dependencies
├── .github/workflows/
│   └── build-and-push.yml           # Builds and pushes to ECR
└── tests/

uh-groupings-ui/                    # EXTERNAL REPOSITORY
├── src/                             # React source code
├── Dockerfile                       # Builds container image
├── package.json                     # Dependencies
├── .github/workflows/
│   └── build-and-push.yml           # Builds and pushes to ECR
└── tests/
```

## Key Points

### What's in example-aws-iac (Infrastructure Repo)
✅ AWS CDK infrastructure code
✅ References to external ECR images
✅ Deployment automation workflows
✅ Documentation about the architecture
✅ Example Dockerfiles (reference only)
✅ Service README files linking to actual repos

### What's NOT in example-aws-iac
❌ API source code (in uh-groupings-api)
❌ UI source code (in uh-groupings-ui)
❌ Actual service Dockerfiles (in respective service repos)
❌ Service dependencies (in respective service repos)
❌ Service tests (in respective service repos)

### services/ Directory Purpose
The `services/` directory serves as **documentation and reference**:
- Shows the expected structure of service repositories
- Provides example Dockerfiles
- Contains README files linking to actual repositories
- Does NOT contain actual application code or source files

## How It Works End-to-End

```
1. API Team Develops
   ├─ Pushes to uh-groupings-api/release-prod
   ├─ GitHub Actions (in uh-groupings-api) builds image
   └─ Pushes to ECR as: uh-groupings-api:release-prod

2. UI Team Develops (Independent)
   ├─ Pushes to uh-groupings-ui/release-prod
   ├─ GitHub Actions (in uh-groupings-ui) builds image
   └─ Pushes to ECR as: uh-groupings-ui:release-prod

3. Infrastructure Team Coordinates
   ├─ Updates app-stack.ts with new image URIs
   ├─ Commits to example-aws-iac
   ├─ GitHub Actions (in example-aws-iac) deploys
   └─ CDK pulls images from ECR and launches services
```

## Repository Links

- **Infrastructure (This Repo)**: example-aws-iac
- **API Service**: https://github.com/uhawaii-system-its-ti-iam/uh-groupings-api/tree/release-prod
- **UI Service**: https://github.com/uhawaii-system-its-ti-iam/uh-groupings-ui/tree/release-prod
