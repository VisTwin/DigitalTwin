#!/bin/bash

# ----------------------------
# Drone Dashboard Auto-Launcher
# ----------------------------

# Change these if needed
DASHBOARD="realtime_drone_dashboard.py"
AGENT="twin_agent.py"
LISTENER="listener.py"

echo "===================================="
echo "     Starting Drone Dashboard"
echo "===================================="

# Get the Jetson Nano WiFi IP
echo "Detecting Jetson Nano WiFi IP..."
IP_ADDR=$(hostname -I | awk '{print $1}')
echo "Jetson Nano WiFi IP: $IP_ADDR"
echo "Open the dashboard at: http://$IP_ADDR:5000"
echo "------------------------------------"

# Start Flask dashboard
python3 "$DASHBOARD" &
DASHBOARD_PID=$!
echo "Dashboard started (PID $DASHBOARD_PID)"
sleep 2

# Start twin_agent publisher
echo "Starting drone ZMQ publisher..."
python3 "$AGENT" &
AGENT_PID=$!
echo "Publisher started (PID $AGENT_PID)"
sleep 1

# Optional listener
ENABLE_LISTENER=false

if [ "$ENABLE_LISTENER" = true ]; then
    echo "Starting telemetry listener..."
    python3 "$LISTENER" &
    LISTENER_PID=$!
    echo "Listener started (PID $LISTENER_PID)"
fi

echo ""
echo "==============================="
echo "   All services are running!"
echo "   Visit: http://$IP_ADDR:5000"
echo "==============================="
echo ""

wait
#!/bin/bash


# Drone Dashboard Auto-Launcher


# Change as needed
DASHBOARD="realtime_drone_dashboard.py"
AGENT="twin_agent.py"
LISTENER="listener.py"

echo "Starting Drone Telemetry Dashboard..."

# Start Flask dashboard
python3 "$DASHBOARD" &
DASHBOARD_PID=$!
echo "Dashboard started (PID $DASHBOARD_PID)"
sleep 2

# Start twin_agent publisher
echo "Starting drone ZMQ publisher..."
python3 "$AGENT" &
AGENT_PID=$!
echo "Publisher started (PID $AGENT_PID)"
sleep 1

# Optional: start the listener
ENABLE_LISTENER=false

if [ "$ENABLE_LISTENER" = true ]; then
    echo "Starting telemetry listener..."
    python3 "$LISTENER" &
    LISTENER_PID=$!
    echo "Listener started (PID $LISTENER_PID)"
fi

echo ""
echo "==============================="
echo "   All services are running!"
echo "   Visit: http://127.0.0.1:5000"
echo "==============================="
echo ""

# Wait for all background processes
wait
