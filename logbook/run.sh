#!/usr/bin/with-contenv bashio

# Create persistent storage directory
mkdir -p /data/logbook

# Start the web application
python3 /app/app.py