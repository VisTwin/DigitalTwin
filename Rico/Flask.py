from flask import Flask, render_template_string, jsonify, request
from datetime import datetime
import threading, time, random

app = Flask(__name__)

# ==========================
# Global telemetry storage
# ==========================
telemetry_data = {
    "altitude": 0.0,
    "speed": 0.0,
    "latitude": 0.0,
    "longitude": 0.0
}

altitude_history = []
telemetry_lock = threading.Lock()

# Control flag
simulate_active = False

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
  <h1>🚁 Drone Telemetry Dashboard</h1>

  <div style="margin-bottom:30px;">
    <h3>Current Telemetry</h3>
    <p>Altitude: <span id="altitude">0</span> m</p>
    <p>Speed: <span id="speed">0</span> m/s</p>
    <p>Latitude: <span id="latitude">0</span></p>
    <p>Longitude: <span id="longitude">0</span></p>
  </div>

  <canvas id="altChart" width="600" height="300"></canvas>

  <h2 style="margin-top:40px;">🧩 Simulation Control</h2>
  <form id="simulationForm" style="display:inline-block; text-align:left;">
    <label>Altitude (m):</label><br>
    <input type="number" id="sim_altitude" step="0.1" required><br><br>
    <label>Speed (m/s):</label><br>
    <input type="number" id="sim_speed" step="0.1" required><br><br>
    <label>Latitude:</label><br>
    <input type="text" id="sim_lat" required><br><br>
    <label>Longitude:</label><br>
    <input type="text" id="sim_lon" required><br><br>
    <button type="submit">Send Simulation Data</button>
  </form>

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
          borderWidth: 2
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
      alert('Simulation started!');
    });

    setInterval(updateTelemetry, 1000);
  </script>
</body>
</html>
"""

# ==========================
# Flask Routes
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
    global simulate_active
    data = request.get_json()
    with telemetry_lock:
        telemetry_data.update({
            "altitude": data.get("altitude", telemetry_data["altitude"]),
            "speed": data.get("speed", telemetry_data["speed"]),
            "latitude": data.get("latitude", telemetry_data["latitude"]),
            "longitude": data.get("longitude", telemetry_data["longitude"]),
        })
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
        if len(altitude_history) > 60:
            altitude_history.pop(0)
    simulate_active = True
    print("[SIM] Manual simulation started:", telemetry_data)
    return jsonify({"status": "Simulation started"})

# ==========================
# Controlled Flight Animation
# ==========================
def controlled_flight_animation():
    global simulate_active
    while True:
        if simulate_active:
            for _ in range(10):  # animate for 10 seconds
                with telemetry_lock:
                    telemetry_data["altitude"] += random.uniform(-0.3, 0.6)
                    telemetry_data["speed"] = max(0, telemetry_data["speed"] + random.uniform(-0.1, 0.3))
                    telemetry_data["latitude"] += random.uniform(-0.00002, 0.00005)
                    telemetry_data["longitude"] += random.uniform(-0.00002, 0.00005)
                    altitude_history.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "altitude": telemetry_data["altitude"]
                    })
                    if len(altitude_history) > 60:
                        altitude_history.pop(0)
                time.sleep(1)
            simulate_active = False  # stop after one animation cycle
        time.sleep(0.2)

threading.Thread(target=controlled_flight_animation, daemon=True).start()

if __name__ == "__main__":
    print("[SERVER] Flask dashboard running at http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
