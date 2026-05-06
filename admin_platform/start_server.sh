#!/bin/bash
echo "Starting EDDA server..."
while true; do
    echo "$(date): Starting uvicorn server"
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level debug
    echo "$(date): Server stopped, restarting in 5 seconds..."
    sleep 5
done
