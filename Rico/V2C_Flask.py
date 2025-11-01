import threading
from threading import Lock
import requests
import speech_recognition as sr
from flask import Flask, request, jsonify
import os, signal
import csv
from datetime import datetime

# ==============================
# THREAD SAFETY AND DATA
# ==============================

# Data shared between the telemetry server thread and the voice command thread
telemetry_data = {"altitude": 0, "battery": 0, "lat": 0, "lon": 0}

# A lock to ensure only one thread reads or writes to telemetry_data at a time
telemetry_lock = Lock()

# ==============================
# TELEMETRY SERVER SECTION
# ==============================

app = Flask(__name__)

@app.route('/telemetry', methods=['POST'])
def telemetry():
    global telemetry_data
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No telemetry data received"}), 400
    
    # Use the lock to safely update the shared data structure
    with telemetry_lock:
        telemetry_data.update(data)
        log_telemetry(telemetry_data)
        print("\nTelemetry Update:")
        print(f" Altitude: {telemetry_data.get('altitude', 0)} m")
        print(f" Battery: {telemetry_data.get('battery', 0)} %")
        print(f" Location: {telemetry_data.get('lat', 0)}, {telemetry_data.get('lon', 0)}")
        print("====================================")
        
    return jsonify({"status": "ok"})

def log_telemetry(data):
    with open("telemetry_log.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.now(), data['altitude'], data['battery'], data['lat'], data['lon']])
        
def run_telemetry_server():
    #can change it back to '10.133.68.115' if required for your setup.
    app.run(host='0.0.0.0', port=5000)

# ==============================
# VOICE COMMAND SECTION
# ==============================

SHORTCUT_URLS = {
    "takeoff": "https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Dji%20Take%20Off",
    "land": "https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Dji%20Land"
}

def send_command(command, url):
    """Utility function to send commands and handle network errors."""
    print(f"\nSending {command} command...")
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        print(f"Command '{command}' sent successfully (HTTP {response.status_code}).")
    except requests.exceptions.RequestException as e:
        print(f"Error sending command '{command}': {e}")

def get_status():
    """Reads and formats the current telemetry data using the lock."""
    with telemetry_lock:
        # Safely read data from the shared dictionary
        alt = telemetry_data.get('altitude', 0)
        bat = telemetry_data.get('battery', 0)
        lat = telemetry_data.get('lat', 0)
        lon = telemetry_data.get('lon', 0)
    
    print("\n--- Current Drone Status ---")
    print(f"Altitude: {alt} meters")
    print(f"Battery: {bat}%")
    print(f"Location: Latitude {lat}, Longitude {lon}")
    print("----------------------------")

def voice_control_loop():
    r = sr.Recognizer()
    mic = sr.Microphone()
    print("\nCalibrating microphone for ambient noise...")

    # Calibrate once before the loop
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=1)

    print("\nVoice Control Active: say 'drone take off', 'drone land', 'drone status', or 'drone exit'")

    while True:
        with mic as source:
            print("\nListening...")
            audio = r.listen(source)

        try:
            cmd = r.recognize_google(audio).lower()
            print(f"You said: {cmd}")

            if "drone" in cmd:
                if "take off" in cmd:
                    send_command("takeoff", SHORTCUT_URLS["takeoff"])
                elif "land" in cmd:
                    send_command("land", SHORTCUT_URLS["land"])
                elif "status" in cmd or "report" in cmd or "battery" in cmd:
                    get_status()
                elif "exit" in cmd:
                    print("\nExiting voice control...")
                    os.kill(os.getpid(), signal.SIGINT)
                    break
                else:
                    print("\nCommand not recognized. Try 'take off', 'land', or 'status'.")
                    
        except sr.UnknownValueError:
            pass  # Ignore unrecognized speech
        except sr.RequestError as e:
            print(f"\nCould not request results from Google Speech Recognition service; {e}")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")


# ==============================
# MAIN ENTRY POINT
# ==============================

if __name__ == '__main__':
    # Run telemetry Flask server in a background thread
    server_thread = threading.Thread(target=run_telemetry_server, daemon=True)
    server_thread.start()
    print("Telemetry server started on port 5000 in background.")

    # Start voice control in the main thread
    voice_control_loop()
    
    print("Program finished.")
