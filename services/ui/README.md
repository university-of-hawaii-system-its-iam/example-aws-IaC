
# UI Service Reference

This directory contains reference documentation for the UI service architecture.

## Actual Service Repository

**Repository:** https://github.com/uhawaii-system-its-ti-iam/uh-groupings-ui/tree/release-prod

The actual UI source code, Dockerfile, and CI/CD workflows are maintained in the `uh-groupings-ui` repository, not in this infrastructure repository.

## Technology Stack

This is a **Spring Boot Java web application**, not React/Node.js:
- **Language:** Java 17
- **Framework:** Spring Boot (with web/MVC)
- **Build Tool:** Maven
- **Base Image:** `eclipse-temurin:17-jre-alpine` (Java runtime)
- **Build Image:** `maven:3.9-eclipse-temurin-17` (Maven + Java compiler)
- **UI Framework:** Thymeleaf, JSP, or similar server-side rendering

## Purpose of This Directory

This directory provides:
- **Example Spring Boot Dockerfile** - Shows how to build Spring Boot JAR files in Docker
- **Multi-stage build pattern** - Build stage with Maven, runtime stage with JRE
- **Reference documentation** - Documents the expected build and deployment process
- **Log directory setup** - Creates `/var/log/application/ui` for persistent logging

## How It Works

1. **UI Team** develops Spring Boot web application in the `uh-groupings-ui` repository
2. **Maven builds** the application into a JAR file (`target/*.jar`)
3. **Dockerfile** (multi-stage):
   - Stage 1 (builder): Uses Maven to compile and package the JAR
   - Stage 2 (runtime): Uses lightweight JRE-Alpine to run the JAR
4. **GitHub Actions** in `uh-groupings-ui` pushes image to AWS ECR
5. **Image tag:** `uh-groupings-ui:release-prod`
6. **Infrastructure team** references this image in CDK:
   ```typescript
   // infra/lib/app-stack.ts
   const uiImage = ecs.ContainerImage.fromRegistry(
     '123456789.dkr.ecr.us-east-1.amazonaws.com/uh-groupings-ui:release-prod'
   );
   ```

## Building Locally (Reference)

This directory's Dockerfile is for reference. To build the actual Spring Boot UI:

```bash
# Clone the UI repository
git clone https://github.com/uhawaii-system-its-ti-iam/uh-groupings-ui.git
cd uh-groupings-ui

# Build the Docker image (requires Maven in project)
docker build -t uh-groupings-ui:release-prod .

# Run locally for testing (Spring Boot on port 3000 as configured)
docker run -p 3000:3000 uh-groupings-ui:release-prod
```

## Build Process

The UI service build process:
1. Maven downloads dependencies from `pom.xml`
2. Maven compiles Java source code
3. Maven packages into executable JAR file
4. Runtime stage copies JAR and runs with JRE
5. Spring Boot starts and serves web pages on port 3000

## Environment Variables

UI service environment variables are injected by CDK during deployment:
- API endpoint URLs (for backend API communication)
- Feature flags
- Application settings
- Authentication configuration
- Spring profiles

These are NOT stored in the Dockerfile but configured in `infra/lib/app-stack.ts`.

## CI/CD Pipeline

The actual CI/CD pipeline is in the `uh-groupings-ui` repository:

1. Code committed to `release-prod` branch
2. GitHub Actions workflow triggered
3. Maven builds Spring Boot JAR
4. Docker image built with tag: `uh-groupings-ui:release-prod`
5. Image pushed to AWS ECR
6. Infrastructure team can then deploy the new image

## Port and Health Checks

- **Port:** 3000 (as configured in application)
- **Health Check:** Spring Boot Actuator endpoint at `/actuator/health`
- **Protocol:** HTTP
- **Health Check Command:** `wget --spider http://localhost:3000/actuator/health`

## Spring Boot Web Application Specifics

- Serves HTML/CSS/JavaScript from Spring Boot (not static CDN)
- Thymeleaf, JSP, or similar for server-side rendering
- Spring MVC controllers serve web pages
- Spring Boot embedded Tomcat application server
- Requires `pom.xml` with Spring Boot web starter
- Spring Boot Actuator dependency needed for health checks
- Startup time typically 5-10 seconds
- JVM heap settings may need tuning for container environments

See the actual `uh-groupings-ui` repository for current configuration and architecture details.
