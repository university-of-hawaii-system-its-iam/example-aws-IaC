#!/bin/sh
set -e

# Log rotation and startup script for UI service
# This script runs logrotate periodically and starts the Java application

# Ensure log directories exist with correct permissions
mkdir -p /var/log/application/ui /logs/Archive
chmod 755 /var/log/application/ui /logs/Archive

# Run logrotate once on startup
logrotate -f /etc/logrotate.d/ui 2>/dev/null || true

# Background process: Run logrotate every 6 hours
(
  while true; do
    sleep 21600  # 6 hours
    logrotate -f /etc/logrotate.d/ui 2>/dev/null || true
  done
) &

# Start the Java application
exec java -jar app.jar

