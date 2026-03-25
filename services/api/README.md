
# API Service Reference

This directory contains reference documentation for the API service architecture.

## Actual Service Repository

**Repository:** https://github.com/uhawaii-system-its-ti-iam/uh-groupings-api/tree/release-prod

The actual API source code, Dockerfile, and CI/CD workflows are maintained in the `uh-groupings-api` repository, not in this infrastructure repository.

## Technology Stack

This is a **Spring Boot Java application**, not Node.js:
- **Language:** Java 17
- **Framework:** Spring Boot
- **Build Tool:** Maven
- **Base Image:** `eclipse-temurin:17-jre-alpine` (Java runtime)
- **Build Image:** `maven:3.9-eclipse-temurin-17` (Maven + Java compiler)

## Purpose of This Directory

This directory provides:
- **Example Spring Boot Dockerfile** - Shows how to build Spring Boot JAR files in Docker
- **Multi-stage build pattern** - Build stage with Maven, runtime stage with JRE
- **Reference documentation** - Documents the expected build and deployment process
- **Log directory setup** - Creates `/var/log/application/api` for persistent logging

## How It Works

1. **API Team** develops Spring Boot application in the `uh-groupings-api` repository
2. **Maven builds** the application into a JAR file (`target/*.jar`)
3. **Dockerfile** (multi-stage):
   - Stage 1 (builder): Uses Maven to compile and package the JAR
   - Stage 2 (runtime): Uses lightweight JRE-Alpine to run the JAR
4. **GitHub Actions** in `uh-groupings-api` pushes image to AWS ECR
5. **Image tag:** `uh-groupings-api:release-prod`
6. **Infrastructure team** references this image in CDK:
   ```typescript
   // infra/lib/app-stack.ts
   const apiImage = ecs.ContainerImage.fromRegistry(
     '123456789.dkr.ecr.us-east-1.amazonaws.com/uh-groupings-api:release-prod'
   );
   ```

## Building Locally (Reference)

This directory's Dockerfile is for reference. To build the actual Spring Boot API:

```bash
# Clone the API repository
git clone https://github.com/uhawaii-system-its-ti-iam/uh-groupings-api.git
cd uh-groupings-api

# Build the Docker image (requires Maven in project)
docker build -t uh-groupings-api:release-prod .

# Run locally for testing (Spring Boot on port 8080 by default)
docker run -p 8080:8080 uh-groupings-api:release-prod
```

## Environment Variables

API service environment variables are injected by CDK during deployment:
- Database connection strings
- API keys and secrets
- Configuration parameters
- Feature flags
- Spring profiles

These are NOT stored in the Dockerfile but configured in `infra/lib/app-stack.ts`.

## CI/CD Pipeline

The actual CI/CD pipeline is in the `uh-groupings-api` repository:

1. Code committed to `release-prod` branch
2. GitHub Actions workflow triggered
3. Maven builds Spring Boot JAR
4. Docker image built with tag: `uh-groupings-api:release-prod`
5. Image pushed to AWS ECR
6. Infrastructure team can then deploy the new image

## Port and Health Checks

- **Port:** 8080 (Spring Boot default)
- **Health Check:** Spring Boot Actuator endpoint at `/actuator/health`
- **Protocol:** HTTP
- **Health Check Command:** `wget --spider http://localhost:8080/actuator/health`

See the actual `uh-groupings-api` repository for current port configuration and health endpoint details.

## Spring Boot Considerations

- Requires `pom.xml` with Maven configuration
- Spring Boot Actuator dependency needed for health checks
- JVM heap settings may need tuning for container environments
- Application properties/YAML configuration via environment variables
- Startup time typically 5-10 seconds (adjust health check start-period if needed)
