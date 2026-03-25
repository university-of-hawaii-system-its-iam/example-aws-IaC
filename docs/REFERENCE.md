# 🚀 QUICK REFERENCE GUIDE

## Three Repositories

### 1️⃣ example-aws-iac (THIS ONE)
**Infrastructure Repository**
- **Link:** (this repository)
- **Owner:** Infrastructure/DevOps Team
- **Contains:**
    - AWS CDK code
    - Deployment workflows
    - Architecture documentation
- **Builds:** ❌ No
- **Deploys:** ✅ Yes (to AWS)
- **References:** ECR images from uh-groupings-api and uh-groupings-ui

### 2️⃣ uh-groupings-api (EXTERNAL)
**API Service Repository**
- **Link:** https://github.com/uhawaii-system-its-ti-iam/uh-groupings-api/tree/release-prod
- **Owner:** API Development Team
- **Contains:**
    - Java/Node.js source code
    - Dockerfile
    - Tests
    - CI/CD build workflow
- **Builds:** ✅ Yes (Docker image)
- **Deploys:** ❌ No (pushes to ECR)
- **Output:** Docker image to AWS ECR

### 3️⃣ uh-groupings-ui (EXTERNAL)
**UI Service Repository**
- **Link:** https://github.com/uhawaii-system-its-ti-iam/uh-groupings-ui/tree/release-prod
- **Owner:** Frontend Development Team
- **Contains:**
    - React source code
    - Dockerfile
    - Tests
    - CI/CD build workflow
- **Builds:** ✅ Yes (Docker image)
- **Deploys:** ❌ No (pushes to ECR)
- **Output:** Docker image to AWS ECR

---

## What Goes Where

### In example-aws-iac ✅
```
✅ AWS CDK infrastructure (infra/lib/*.ts)
✅ Deployment workflows (.github/workflows/*.yml)
✅ Architecture documentation (docs/architecture/)
✅ README files and guides (README.md)
✅ Example Dockerfiles (reference only)
✅ Links to service repositories
```

### NOT in example-aws-iac ❌
```
❌ API source code → goes to uh-groupings-api
❌ UI source code → goes to uh-groupings-ui
❌ Service Dockerfiles → in service repos
❌ Service tests → in service repos
❌ Service dependencies → in service repos
```

---

## Deployment Sequence

```
Step 1: Service Teams Develop
   API Team (uh-groupings-api)  commits  → GitHub
   UI Team (uh-groupings-ui)    commits  → GitHub

Step 2: Service Teams Build & Push Images
   API GitHub Actions  → builds image → pushes to ECR
   UI GitHub Actions   → builds image → pushes to ECR

Step 3: Infrastructure Team Deploys
   Infrastructure team  → updates app-stack.ts → commits to example-aws-iac
   GitHub Actions       → CDK deploy          → AWS ECS

Step 4: Services Run
   AWS ECR              → pulls images
   AWS ECS              → launches containers
   Users                → access services
```

---

## Quick Navigation

### API Documentation
📍 **This Repo:** `/services/api/README.md`
- Explains the multi-repo architecture
- Links to actual API repository
- Shows how API is built and deployed

### UI Documentation
📍 **This Repo:** `/services/ui/README.md`
- Explains the multi-repo architecture
- Links to actual UI repository
- Shows how UI is built and deployed

### Architecture Deep Dive
📍 **This Repo:** `/docs/architecture/README.md`
- Infrastructure stack composition
- Deployment flow diagrams
- Service integration points

### Project Overview
📍 **This Repo:** `/README.md`
- Complete architecture overview
- Team workflows
- Repository relationships

---

## Key Files to Know

| File                          | Purpose                      | Audience                |
|-------------------------------|------------------------------|-------------------------|
| `/README.md`                  | Project overview             | Everyone                |
| `/services/api/README.md`     | API reference                | API Team + Infra Team   |
| `/services/ui/README.md`      | UI reference                 | UI Team + Infra Team    |
| `/docs/ARCHITECTURE.md`       | Architecture details         | Architects + Infra Team |
| `/docs/STRUCTURE.md`          | Project Organization details | Architects + Infra Team |
| `/infra/lib/app-stack.ts`     | Service deployment config    | Infra Team              |
| `/infra/lib/network-stack.ts` | Network infrastructure       | Infra Team              |
| `/infra/lib/data-stack.ts`    | Data infrastructure          | Infra Team              |

---

## Important Concepts

### 🐳 Docker Images (Not Source Code)
Services are deployed as **Docker images**, not as source code.
- Built in service repositories
- Pushed to AWS ECR
- Referenced by CDK in app-stack.ts
- Pulled by ECS at runtime

### 🏗️ Infrastructure as Code (CDK)
All AWS resources defined in **TypeScript code**.
- Version controlled in Git
- Reviewed like any code
- Deployed by GitHub Actions
- Reproducible deployments

### 🔗 Polyrepo Architecture
Teams work in **separate repositories**.
- API team owns uh-groupings-api
- UI team owns uh-groupings-ui
- Infra team owns example-aws-iac
- Teams can work independently

---

## URLs to Remember

| Component | URL |
|-----------|-----|
| API Repository | https://github.com/uhawaii-system-its-ti-iam/uh-groupings-api/tree/release-prod |
| UI Repository | https://github.com/uhawaii-system-its-ti-iam/uh-groupings-ui/tree/release-prod |
| Infrastructure | (this repository) |

---

## When to Look at Each Repository

### uh-groupings-api
- 📝 Writing API code
- 🐳 Creating/updating Dockerfile
- 🧪 Writing API tests
- 🔧 Configuring CI/CD build workflow

### uh-groupings-ui
- 🎨 Writing UI components
- 🎨 Styling
- 🐳 Creating/updating Dockerfile
- 🧪 Writing UI tests
- 🔧 Configuring CI/CD build workflow

### example-aws-iac
- 🏗️ Designing AWS infrastructure
- 📝 Writing CDK code
- 🔧 Configuring deployment workflows
- 📚 Writing architecture documentation
- 🔗 Referencing new service images

---

## One-Liner Summaries

**example-aws-iac:** "We manage the AWS infrastructure and deployment of services from ECR"

**uh-groupings-api:** "We build and publish the API Docker image to ECR"

**uh-groupings-ui:** "We build and publish the UI Docker image to ECR"

---

## Need Help?

### Unsure what goes where?
→ Read `/README.md` section "Multi-Repository Architecture"

### Want API details?
→ See `/services/api/README.md` (or visit uh-groupings-api repo)

### Want UI details?
→ See `/services/ui/README.md` (or visit uh-groupings-ui repo)

### Need architecture details?
→ Check `/docs/architecture/README.md`

### Building services locally?
→ See service READMEs for build instructions

---

✅ **You now understand the complete architecture!** ✅
