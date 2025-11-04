from flask import Flask, request, jsonify, render_template_string
import threading, requests, csv, os
from datetime import datetime

# ==============================
# GLOBAL TELEMETRY DATA
# ==============================
telemetry_data = {"altitude": 0, "battery": 0, "lat": 0, "lon": 0}
altitude_history = []
telemetry_lock = threading.Lock()

# ==============================
# FLASK TELEMETRY SERVER
# ==============================
app = Flask(__name__)

PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>Drone Telemetry Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial; background-color:#0e1117; color:#f0f0f0; text-align:center; padding-top:40px;}
        .card { display:inline-block; background:#1c1f26; border-radius:15px; padding:20px 40px; margin:10px; box-shadow:0 0 10px #000;}
        h1 { color:#00d1b2; }
        canvas { background:#1c1f26; border-radius:10px; padding:10px; margin-top:20px;}
    </style>
</head>
<body>
    <h1>Drone Telemetry Dashboard</h1>
    <div class="card"><p>Altitude: <b id="altitude">0</b> m</p></div>
    <div class="card"><p>Battery: <b id="battery">0</b> %</p></div>
    <div class="card"><p>Latitude: <b id="lat">0</b></p></div>
    <div class="card"><p>Longitude: <b id="lon">0</b></p></div>

    <h2 style="color:#00d1b2;">Altitude (Last 60s)</h2>
    <canvas id="altChart" width="800" height="400"></canvas>

    <script>
        const ctx = document.getElementById('altChart').getContext('2d');
        const chart = new Chart(ctx, {
            type:'line',
            data:{ labels:[], datasets:[{ label:'Altitude (m)', data:[], borderColor:'#00d1b2', backgroundColor:'rgba(0,209,178,0.2)', fill:true, tension:0.3, borderWidth:2 }] },
            options:{ scales:{y:{beginAtZero:true}, x:{ticks:{color:'#aaa'}, grid:{color:'#333'}}}, plugins:{legend:{labels:{color:'#f0f0f0'}}} }
        });

        async function updateTelemetry(){
            const res = await fetch('/telemetry_data');
            const data = await res.json();
            document.getElementById('altitude').textContent = data.altitude.toFixed(2);
            document.getElementById('battery').textContent = data.battery.toFixed(1);
            document.getElementById('lat').textContent = data.lat.toFixed(6);
            document.getElementById('lon').textContent = data.lon.toFixed(6);
        }

        async function updateChart(){
            const res = await fetch('/altitude_data');
            const data = await res.json();
            chart.data.labels = data.map(p => p.time);
            chart.data.datasets[0].data = data.map(p => p.altitude);
            chart.update();
        }

        setInterval(()=>{updateTelemetry();updateChart();},1000);
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(PAGE)

@app.route('/telemetry_data')
def telemetry_data_endpoint():
    with telemetry_lock:
        return jsonify(telemetry_data)

@app.route('/altitude_data')
def altitude_data():
    with telemetry_lock:
        return jsonify(altitude_history)

@app.route('/update_telemetry', methods=['POST'])
def telemetry():
    data = request.get_json(https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Update%20Telemetry)  # <-- just parse incoming JSON
    if not data:
        return jsonify({"error": "No telemetry data received"}), 400
    
    print("📡 Telemetry Received:")
    print(f"Altitude: {data.get('altitude')} m")
    print(f"Battery:  {data.get('battery')} %") 
    print(f"Location: {data.get('lat')}, {data.get('lon')}")

def log_telemetry(data):
    file_exists = os.path.isfile("telemetry_log.csv")
    with open("telemetry_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "altitude", "battery", "lat", "lon"])
        writer.writerow([datetime.now(), data["altitude"], data["battery"], data["lat"], data["lon"]])

# ==============================
# OPTIONAL: send telemetry to server from Python (for testing)
# ==============================
def send_shortcut(payload):
    """Simulate iPad Shortcut sending telemetry to Flask endpoint."""
    try:
        url = "http://127.0.0.1:5000/update_telemetry"
        r = requests.post(url, json=payload, timeout=5)
        print(f"[SEND TEST] Status: {r.status_code}, Response: {r.text}")
    except Exception as e:
        print("[SEND TEST ERROR]", e)

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    print("Telemetry dashboard running at: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
