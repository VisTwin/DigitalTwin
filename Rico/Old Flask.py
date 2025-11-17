from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import threading
import zmq
import time

app = Flask(__name__)

# ==========================
# Global Telemetry Storage
# ==========================
telemetry_data = {
    "altitude": 0.0,
    "speed": 0.0,
    "latitude": 0.0,
    "longitude": 0.0
}

altitude_history = []
telemetry_lock = threading.Lock()

# ==========================
# HTML Template
# ==========================
dashboard_html = """
<!DOCTYPE html>
<html>
<head>
  <title>Drone Telemetry Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body style="font-family:Arial; text-align:center; margin:40px;">
  <h1> Drone Telemetry Dashboard</h1>

  <!-- Manual Input Form -->
  <h2> Manual Telemetry Input</h2>
  <form id="simulationForm" style="display:inline-block; text-align:left; margin-bottom:30px;">
    <label>Altitude (m):</label><br>
    <input type="number" id="sim_altitude" step="0.1" required><br><br>
    <label>Speed (m/s):</label><br>
    <input type="number" id="sim_speed" step="0.1" required><br><br>
    <label>Latitude:</label><br>
    <input type="text" id="sim_lat" required><br><br>
    <label>Longitude:</label><br>
    <input type="text" id="sim_lon" required><br><br>
    <button type="submit">Update Telemetry</button>
  </form>

  <!-- Live Telemetry Display -->
  <div style="margin-bottom:30px;">
    <h3>Live Telemetry</h3>
    <p>Altitude: <span id="altitude">0</span> m</p>
    <p>Speed: <span id="speed">0</span> m/s</p>
    <p>Latitude: <span id="latitude">0</span></p>
    <p>Longitude: <span id="longitude">0</span></p>
  </div>

  <!-- Altitude Chart -->
  <canvas id="altChart" width="600" height="300"></canvas>

  <script>
    async function updateTelemetry() {
      const res = await fetch('/telemetry');
      const data = await res.json();
      document.getElementById('altitude').textContent = data.altitude.toFixed(2);
      document.getElementById('speed').textContent = data.speed.toFixed(2);
      document.getElementById('latitude').textContent = data.latitude.toFixed(6);
      document.getElementById('longitude').textContent = data.longitude.toFixed(6);
      updateChart(data.history);
    }

    const ctx = document.getElementById('altChart').getContext('2d');
    const chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Altitude (m)',
          data: [],
          borderColor: 'blue',
          borderWidth: 2,
          fill: false
        }]
      },
      options: {
        animation: false,
        scales: { y: { beginAtZero: true } }
      }
    });

    function updateChart(history) {
      chart.data.labels = history.map(h => h.time);
      chart.data.datasets[0].data = history.map(h => h.altitude);
      chart.update();
    }

    // Manual Input Handler
    document.getElementById('simulationForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = {
        altitude: parseFloat(document.getElementById('sim_altitude').value),
        speed: parseFloat(document.getElementById('sim_speed').value),
        latitude: parseFloat(document.getElementById('sim_lat').value),
        longitude: parseFloat(document.getElementById('sim_lon').value)
      };
      await fetch('/simulate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
      });
      await updateTelemetry();
    });

    setInterval(updateTelemetry, 1500);
  </script>
</body>
</html>
"""

# ==========================
# Flask API Routes
# ==========================
@app.route("/")
def index():
    return render_template_string(dashboard_html)

@app.route("/telemetry")
def telemetry():
    with telemetry_lock:
        return jsonify({
            **telemetry_data,
            "history": altitude_history
        })

@app.route("/simulate", methods=["POST"])
def simulate():
    data = request.get_json()
    with telemetry_lock:
        telemetry_data.update({
            "altitude": data["altitude"],
            "speed": data["speed"],
            "latitude": data["latitude"],
            "longitude": data["longitude"]
        })
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
    return jsonify({"status": "Telemetry updated"})


# ==========================
# Background ZeroMQ Listener
# ==========================
def zmq_listener():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    socket.connect("tcp://localhost:5556")
    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("[ZMQ] Listening for drone telemetry...")

    while True:
        message = socket.recv_json()
        print("[ZMQ] Received:", message)

        with telemetry_lock:
            telemetry_data["altitude"] = message["z"]
            telemetry_data["speed"] = (message["vx"]**2 + message["vy"]**2 + message["vz"]**2) ** 0.5
            telemetry_data["latitude"] = message["x"]
            telemetry_data["longitude"] = message["y"]

            altitude_history.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "altitude": telemetry_data["altitude"]
            })

            if len(altitude_history) > 60:
                altitude_history.pop(0)


# Start ZMQ Listener Thread
listener_thread = threading.Thread(target=zmq_listener, daemon=True)
listener_thread.start()

# ==========================
# Start Server
# ==========================
if __name__ == "__main__":
    print("[SERVER] Flask dashboard running at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

