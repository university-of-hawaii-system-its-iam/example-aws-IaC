# Stage 1: Build Stage
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy source code
COPY . .

# Build the Spring Boot application
RUN mvn clean package -DskipTests

# Stage 2: Runtime Stage
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Install logrotate for log rotation
RUN apk add --no-cache logrotate

# Copy the built JAR from builder stage
COPY --from=builder /app/target/*.jar app.jar

# Create log and archive directories with proper permissions
RUN mkdir -p /var/log/application/ui /logs/Archive && \
    chmod 755 /var/log/application/ui /logs/Archive

# Copy logrotate configuration
COPY logrotate-ui.conf /etc/logrotate.d/ui

# Copy logback configuration (optional, for Spring Boot log rotation)
COPY logback-spring.xml /app/logback-spring.xml

# Copy entrypoint script for log rotation and application startup
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 3000

# Health check (Spring Boot actuator endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:3000/actuator/health || exit 1

# Start the application with log rotation
ENTRYPOINT ["/app/entrypoint.sh"]
