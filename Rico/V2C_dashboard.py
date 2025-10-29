import threading
import requests
import speech_recognition as sr
from flask import Flask, request, jsonify

# ==============================
# TELEMETRY SERVER SECTION
# ==============================

app = Flask(__name__)
telemetry_data = {"altitude": 0, "battery": 0, "lat": 0, "lon": 0}

@app.route('/telemetry', methods=['POST'])
def telemetry():
    global telemetry_data
    data = request.get_json()
    if not data:
        return jsonify({"error": "No telemetry data received"}), 400
    
    telemetry_data.update(data)
    print("\nTelemetry Update:")
    print(f" Altitude: {telemetry_data.get('altitude')} m")
    print(f" Battery:  {telemetry_data.get('battery')} %")
    print(f" Location: {telemetry_data.get('lat')}, {telemetry_data.get('lon')}")
    print("====================================")
    return jsonify({"status": "ok"})

def run_telemetry_server():
    app.run(host='10.133.68.115', port=5000)

# ==============================
# VOICE COMMAND SECTION
# ==============================

SHORTCUT_URLS = {
    "takeoff": "https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Dji%20Take%20Off",
    "land": "https://api.pushcut.io/3CsuPL31cbY8gkSfKlG73/notifications/Dji%20Land"
}

def voice_control_loop():
    r = sr.Recognizer()
    mic = sr.Microphone()
    print("\nVoice Control Active: say 'take off', 'land', or 'exit'")

    while True:
        with mic as source:
            print("\nListening...")
            audio = r.listen(source)
        try:
            cmd = r.recognize_google(audio).lower()
            print(f"You said: {cmd}")

            if "take off" in cmd:
                print("\nSending takeoff command to iPad...")
                requests.get(SHORTCUT_URLS["takeoff"])
            elif "land" in cmd:
                print("\nSending land command to iPad...")
                requests.get(SHORTCUT_URLS["land"])
            elif "exit" in cmd:
                print("\nExiting voice control...")
                break
            else:
                print("\nCommand not recognized.")
        except Exception as e:
            print("\nError:", e)

# ==============================
# MAIN ENTRY POINT
# ==============================

if __name__ == '__main__':
    # Run telemetry Flask server in a background thread
    server_thread = threading.Thread(target=run_telemetry_server, daemon=True)
    server_thread.start()

    # Start voice control
    voice_control_loop()
