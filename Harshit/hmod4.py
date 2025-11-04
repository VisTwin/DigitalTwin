from flask import Flask, request, render_template_string, jsonify, send_file, Response
import numpy as np
import pandas as pd
import time
import threading
import math
import cv2
from quanser.hardware import HIL
import webbrowser
import os
import atexit

# Corrected Flask initialization
app = Flask(__name__)  # Use __name__ with double underscores
CSV_FILE_PATH = "tank_data.csv"

# State management with thread safety
state_lock = threading.Lock()
state = {
    "running": False,
    "data": []
}

# Camera configuration
# Default to 1 for external webcam. Ensure this is set correctly in your environment.
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 1))
camera = None

def initialize_camera():
    global camera
    
    # 1. Try the specified CAMERA_INDEX using the CAP_DSHOW backend (often better for external cameras on Windows)
    print(f"Attempt 1: Trying CAMERA_INDEX {CAMERA_INDEX} with CAP_DSHOW...")
    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    used_index = CAMERA_INDEX

    if not camera.isOpened():
        print(f"Attempt 2: Failed DSHOW. Trying CAMERA_INDEX {CAMERA_INDEX} with CAP_MSMF...")
        # 2. Try the specified CAMERA_INDEX using the CAP_MSMF backend (your original attempt)
        camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)

    if not camera.isOpened():
        print("Attempt 3: Failed to open specified index. Starting fallback search with CAP_DSHOW...")
        # 3. Fallback search: Iterate through indices 0 to 4 using CAP_DSHOW
        for index in range(5):
            if index == CAMERA_INDEX and index < 2:  # Avoid re-testing the specified index unless it's the internal one (0)
                continue
            
            temp_camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            
            # Check if this camera is different from the intended CAMERA_INDEX
            if temp_camera.isOpened():
                # A quick check to see if we found a working camera
                print(f"Found a working camera with CAP_DSHOW at index {index}")
                # We stop at the first one found, assuming the user will adjust CAMERA_INDEX if it's the wrong one
                camera = temp_camera
                used_index = index
                break
            temp_camera.release() # Release to avoid resource lock
        
    if not camera or not camera.isOpened():
        print("Error: No camera found on DSHOW fallback. Trying MSMF fallback...")
        # 4. Fallback search with MSMF as a last resort
        for index in range(5):
            temp_camera = cv2.VideoCapture(index, cv2.CAP_MSMF)
            if temp_camera.isOpened():
                print(f"Found a working camera with CAP_MSMF at index {index}")
                camera = temp_camera
                used_index = index
                break
            temp_camera.release()

    if camera and camera.isOpened():
        print(f"**Successfully using camera at index {used_index}**")
        return True
    else:
        print("**Error: No camera found. Video feed will not be available.**")
        return False

def release_camera():
    global camera
    if camera and camera.isOpened():
        camera.release()
        print("Camera released")

# Register camera cleanup on exit
atexit.register(release_camera)

# Initialize camera at startup
initialize_camera()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Coupled Tank Experiment</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .control-panel, .main-layout { width: 100%; margin-bottom: 20px; }
        .control-panel form { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; align-items: center; }
        .feedback-panel { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
        .value-box {
            border: 1px solid #ccc;
            padding: 5px 10px;
            background-color: #f9f9f9;
            border-radius: 5px;
            min-height: 38px;
            display: flex;
            align-items: center;
        }
        .main-layout { display: flex; gap: 20px; justify-content: space-between; }
        .camera-box, .tank-box { flex: 1; }
        .tank-visual {
            width: 100px;
            height: 500px;
            border: 2px solid #333;
            position: relative;
            margin: auto;
            background-color: #e0e0e0;
        }
        .water-fill {
            position: absolute;
            bottom: 0;
            width: 100%;
            background-color: #4fc3f7;
            transition: height 0.5s ease-in-out;
        }
        .tank-label {
            text-align: center;
            margin-top: 10px;
            font-weight: bold;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h2>Coupled Tank Experiment</h2>
    <div class="control-panel">
        <form onsubmit="startSimulation(); return false;">
            <div>
                <label>Base Voltage (V):</label>
                <input type="number" id="base_voltage" value="5" step="0.1" min="0" max="10">
            </div>
            <div>
                <label>Frequency (Hz):</label>
                <input type="number" id="frequency" value="0.2" step="0.01" min="0" max="10">
            </div>
            <div>
                <label>Amplitude (V):</label>
                <input type="number" id="amplitude" value="1" step="0.1" min="0" max="5">
            </div>
            <div style="margin-top: 22px;">
                <input type="submit" value="Start Simulation">
                <input type="button" value="Stop Simulation" onclick="stopSimulation()">
            </div>
        </form>
    </div>

    <div class="feedback-panel">
        <div class="value-box"><strong>Time:</strong> <span id="time_val">--</span> s</div>
        <div class="value-box"><strong>Tank 1 Level:</strong> <span id="tank1_val">--</span> cm</div>
        <div class="value-box"><strong>Tank 2 Level:</strong> <span id="tank2_val">--</span> cm</div>
        <div class="value-box"><a href="/download">Download CSV Data</a></div>
    </div>

    <div class="main-layout">
        <div class="camera-box" style="border: 2px solid #555; border-radius: 10px; padding: 10px;">
            <h3>Physical Experiment</h3>
            {% if camera_available %}
            <img src="/video_feed" width="100%">
            {% else %}
            <p>Error: Camera not available</p>
            {% endif %}
        </div>
        <div class="tank-box" style="border: 2px solid #555; border-radius: 10px; padding: 10px;">
            <h3 style="text-align:center;">Virtual Experiment</h3>
            <div style="display: flex; justify-content: space-around;">
                <div>
                    <div class="tank-visual" style="position: relative;">
                        <div style="position: absolute; left: -35px; bottom: 0; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                            {% for i in range(50, -1, -5) %}
                                <span style="font-size:14px; font-weight: bold;">{{ i }}</span>
                            {% endfor %}
                        </div>
                        <div id="tank1_fill" class="water-fill" style="height:0px"></div>
                    </div>
                    <div class="tank-label">Tank 1</div>
                </div>
                <div>
                    <div class="tank-visual" style="position: relative;">
                        <div style="position: absolute; left: -35px; bottom: 0; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                            {% for i in range(50, -1, -5) %}
                                <span style="font-size:14px; font-weight: bold;">{{ i }}</span>
                            {% endfor %}
                        </div>
                        <div id="tank2_fill" class="water-fill" style="height:0px"></div>
                    </div>
                    <div class="tank-label">Tank 2</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function startSimulation() {
            const base = document.getElementById("base_voltage").value;
            const freq = document.getElementById("frequency").value;
            const amp = document.getElementById("amplitude").value;

            fetch("/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ base_voltage: base, frequency: freq, amplitude: amp })
            });

            const interval = setInterval(() => {
                fetch("/data")
                .then(res => res.json())
                .then(json => {
                    if (json.data.length > 0) {
                        const latest = json.data[json.data.length - 1];
                        const tank1 = latest[1];
                        const tank2 = latest[2];
                        document.getElementById("time_val").textContent = latest[0];
                        document.getElementById("tank1_val").textContent = tank1;
                        document.getElementById("tank2_val").textContent = tank2;
                        const CM_TO_PX = 10;
                        document.getElementById("tank1_fill").style.height = (tank1 * CM_TO_PX) + "px";
                        document.getElementById("tank2_fill").style.height = (tank2 * CM_TO_PX) + "px";
                    }
                    if (!json.running) clearInterval(interval);
                });
            }, 500); // Reduced to 500ms for smoother updates
        }

        function stopSimulation() {
            fetch("/stop", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
        }
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, camera_available=camera and camera.isOpened())

@app.route("/start", methods=["POST"])
def start_sim():
    params = request.get_json()
    try:
        base_voltage = float(params["base_voltage"])
        frequency = float(params["frequency"])
        amplitude = float(params["amplitude"])
        if not (0 <= base_voltage <= 10 and 0 <= frequency <= 10 and 0 <= amplitude <= 5):
            return "Invalid parameters: base_voltage [0,10], frequency [0,10], amplitude [0,5]", 400
    except (KeyError, ValueError):
        return "Invalid or missing parameters", 400
    with state_lock:
        if state["running"]:
            return "Simulation already running", 400
        state["data"] = []
        state["running"] = True
    thread = threading.Thread(target=run_simulation, args=(base_voltage, frequency, amplitude))
    thread.start()
    return "Started", 200

@app.route("/stop", methods=["POST"])
def stop_sim():
    with state_lock:
        if not state["running"]:
            return "No simulation running", 400
        state["running"] = False
    return "Stopped", 200

@app.route("/data")
def get_data():
    with state_lock:
        return jsonify({"running": state["running"], "data": state["data"]})

@app.route("/download")
def download_csv():
    with state_lock:
        df = pd.DataFrame(state["data"], columns=["Time (s)", "Tank 1 Height (cm)", "Tank 2 Height (cm)"])
    if df.empty:
        return "No data available", 400
    df.index += 1
    df.to_csv(CSV_FILE_PATH, index_label="Time (s)")
    return send_file(CSV_FILE_PATH, as_attachment=True)

@app.route('/video_feed')
def video_feed():
    if not camera or not camera.isOpened():
        return Response("Camera not available", status=503)
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def gen_frames():
    if not camera or not camera.isOpened():
        print("Error: Camera not accessible")
        return
    while True:
        success, frame = camera.read()
        if not success:
            print("Error: Failed to capture frame")
            # Try to re-initialize the camera if it fails to capture
            # release_camera()
            # initialize_camera()
            # if not camera or not camera.isOpened():
            #    break
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        if ret:
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def run_simulation(base_voltage, frequency, amplitude):
    duration = 30.0
    dt = 1.0
    slope = 9.8
    offset = 0.0
    steps = int(duration / dt)
    card = HIL()
    try:
        card.open("q2_usb", "0")
    except Exception as e:
        print(f"Error opening HIL card: {e}")
        with state_lock:
            state["running"] = False
        return
    output_channel = np.array([0], dtype=np.uint32)
    input_channels = np.array([0, 1], dtype=np.uint32)
    try:
        for i in range(steps):
            with state_lock:
                if not state["running"]:
                    break
            t = i * dt
            try:
                voltage = base_voltage + amplitude * math.sin(2 * math.pi * frequency * t)
                card.write_analog(output_channel, 1, np.array([voltage], dtype=np.float64))
                buffer = np.zeros(2, dtype=np.float64)
                card.read_analog(input_channels, 2, buffer)
                tank1 = slope * buffer[0] + offset
                tank2 = slope * buffer[1] + offset
                with state_lock:
                    state["data"].append((round(t, 1), round(tank1, 2), round(tank2, 2)))
            except Exception as e:
                print(f"Error in simulation step {i}: {e}")
            time.sleep(dt)
        card.write_analog(output_channel, 1, np.array([0.0], dtype=np.float64))
    finally:
        card.close()
        with state_lock:
            state["running"] = False

def open_browser():
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    threading.Timer(1.0, open_browser).start()
    app.run(debug=True, use_reloader=False) # Important: use_reloader=False to prevent camera re-initialization on save