import os
import signal
import threading
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit

# ================= CONFIG =================
SHORTCUT_URLS = {
    "takeoff": "https://example.com/takeoff",
    "land": "https://example.com/land",
}
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

telemetry_data = {
    "altitude": 0.0,
    "battery": 100,
    "speed": 0.0,
    "latitude": 0.0,
    "longitude": 0.0,
}

# ================= TELEMETRY ROUTE =================
@app.route('/telemetry', methods=['POST'])
def telemetry():
    data = request.get_json()
    if data:
        telemetry_data.update(data)
        # Push update to dashboard in real time
        socketio.emit('telemetry_update', telemetry_data)
        print("Telemetry received:", telemetry_data)
    return jsonify(success=True)

# ================= DASHBOARD =================
@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Drone Telemetry Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #0e1117;
                color: #e0e0e0;
                text-align: center;
                margin: 0;
                padding: 0;
            }
            h1 {
                background: #1a1d23;
                padding: 10px;
                margin: 0;
            }
            .container {
                display: flex;
                flex-di
