from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import threading, csv, os, time
from datetime import datetime

app = Flask(__name__)

telemetry_data = {"altitude": 0, "battery": 100, "lat": 0, "lon": 0}
altitude_history = []
telemetry_lock = threading.Lock()

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
        form { background:#1c1f26; padding:20px; border-radius:15px; margin:20px auto; width:320px; }
        input { margin:5px; padding:5px; width:90%; border-radius:5px; border:none; }
        button { margin-top:10px; padding:8px 16px; border:none; background:#00d1b2; color:#fff; border-radius:5px; cursor:pointer; }
        button:hover { background:#00a896; }
        .sim-section { background:#1c1f26; border-radius:15px; padding:20px; width:320px; margin:20px auto; }
    </style>
</head>
<body>
    <h1>Drone Telemetry Dashboard</h1>

    <h2 style="color:#00d1b2;">Manual Telemetry Input</h2>
    <form action="/manual_update" method="post">
        <input type="number" step="0.1" name="altitude" placeholder="Altitude (m)" required><br>
        <input type="number" step="0.1" name="battery" placeholder="Battery (%)" required><br>
        <input type="number" step="0.000001" name="lat" placeholder="Latitude" required><br>
        <input type="number" step="0.000001" name="lon" placeholder="Longitude" required><br>
        <button type="submit">Update Telemetry</button>
    </form>

    <div class="sim-section">
        <h2 style="color:#00d1b2;">Simulate Drone Movement</h2>
        <input id="sim_pattern" placeholder="Enter pattern (e.g. up down up)" style="width:90%"><br>
        <input id="sim_amplitude" type="number" placeholder="Step (m)" value="5" style="width:90%"><br>
        <button onclick="simulateDrone()">Start Simulation</button>
        <p id="sim_status"></p>
    </div>

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

        async function sendTelemetry(alt){
            const res = await fetch('/update_telemetry', {
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify({altitude:alt, battery:100, lat:0, lon:0})
            });
            const txt = await res.text();
            document.getElementById('sim_status').textContent = txt;
        }

        async function simulateDrone(){
            let pattern = document.getElementById('sim_pattern').value.trim().split(" ");
            let step = parseFloat(document.getElementById('sim_amplitude').value) || 5;
            if(pattern.length === 0){ pattern = ['up','down']; }

            let currentAlt = parseFloat(document.getElementById('altitude').textContent) || 0;
            document.getElementById('sim_status').textContent = "Simulating...";

            for(const move of pattern){
                if(move.toLowerCase() === 'up') currentAlt += step;
                if(move.toLowerCase() === 'down') currentAlt -= step;
                await sendTelemetry(currentAlt);
                await new Promise(r => setTimeout(r, 1000));
            }
            document.getElementById('sim_status').textContent = "Simulation complete!";
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
    data = request.get_json()
    if not data:
        return "No data received", 400
    with telemetry_lock:
        for k in telemetry_data:
            if k in data:
                telemetry_data[k] = float(data[k])
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": telemetry_data["altitude"]
        })
        if len(altitude_history) > 60:
            altitude_history.pop(0)
    return "Telemetry updated!"

@app.route('/manual_update', methods=['POST'])
def manual_update():
    data = {
        "altitude": float(request.form.get("altitude", 0)),
        "battery": float(request.form.get("battery", 0)),
        "lat": float(request.form.get("lat", 0)),
        "lon": float(request.form.get("lon", 0))
    }

    with telemetry_lock:
        telemetry_data.update(data)
        altitude_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "altitude": data["altitude"]
        })
        if len(altitude_history) > 60:
            altitude_history.pop(0)

    log_telemetry(data)
    return redirect(url_for('index'))

def log_telemetry(data):
    file_exists = os.path.isfile("telemetry_log.csv")
    with open("telemetry_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "altitude", "battery", "lat", "lon"])
        writer.writerow([datetime.now(), data["altitude"], data["battery"], data["lat"], data["lon"]])

if __name__ == "__main__":
    print("🌍 Telemetry dashboard running at: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
