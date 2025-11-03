import requests, threading, socket, json
import speech_recognition as sr
from flask import Flask, request, jsonify, render_template_string
import os, signal, csv
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

def log_telemetry(data):
    file_exists = os.path.isfile("telemetry_log.csv")
    with open("telemetry_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "altitude", "battery", "lat", "lon"])
        writer.writerow([datetime.now(), data["altitude"], data["battery"], data["lat"], data["lon"]])

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False)

# ==============================
# UDP TELEMETRY RECEIVER
# ==============================
def udp_listener():
    UDP_IP = "0.0.0.0"
    UDP_PORT = 14550
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"[UDP] Listening for telemetry on port {UDP_PORT}...")

    while True:
        try:
            msg, _ = sock.recvfrom(1024)
            data = json.loads(msg.decode("utf-8"))
            with telemetry_lock:
                for key in telemetry_data:
                    if key in data:
                        telemetry_data[key] = data[key]
                altitude_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "altitude": telemetry_data["altitude"]
                })
                if len(altitude_history) > 60:
                    altitude_history.pop(0)
            log_telemetry(telemetry_data)
        except Exception as e:
            print("[UDP ERROR]", e)

# ==============================
# VOICE COMMAND SECTION
# ==============================
SHORTCUT_URLS = {
    "takeoff": "https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Dji%20Take%20Off",
    "land": "https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Dji%20Land"
}

def send_command(command, url):
    try:
        print(f"\n[CMD] Sending: {command}")
        requests.post(url, timeout=3)
    except Exception as e:
        print(f"Error sending command '{command}': {e}")

def get_status():
    with telemetry_lock:
        print("\n--- TELEMETRY STATUS ---")
        for k, v in telemetry_data.items():
            print(f"{k}: {v}")
        print("------------------------")

def voice_control_loop():
    r = sr.Recognizer()
    mic = sr.Microphone()
    print("\nCalibrating microphone...")
    with mic as source:
        r.adjust_for_ambient_noise(source, duration = .5)
    print("Voice Control Ready (say 'drone take off', 'land', 'status', or 'exit').")

    while True:
        with mic as source:
            print("\nListening...")
            audio = r.listen(source)
        try:
            cmd = r.recognize_google(audio).lower()
            print(f"You said: {cmd}")
            if "drone take off" in cmd:
                send_command("takeoff", SHORTCUT_URLS["takeoff"])
            elif "drone land" in cmd:
                send_command("land", SHORTCUT_URLS["land"])
            elif "status" in cmd:
                get_status()
            elif "exit" in cmd:
                print("Exiting voice control...")
                os.kill(os.getpid(), signal.SIGINT)
                break
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"Voice recognition error: {e}")

# ==============================
# MAIN ENTRY POINT
# ==============================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=udp_listener, daemon=True).start()
    print("Telemetry dashboard running at: http://127.0.0.1:5000")
    voice_control_loop()
