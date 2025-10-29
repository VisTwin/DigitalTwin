from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/telemetry', methods=['POST'])
def telemetry():
    data = request.get_json()  # <-- just parse incoming JSON
    if not data:
        return jsonify({"error": "No telemetry data received"}), 400
    
    print("📡 Telemetry Received:")
    print(f"Altitude: {data.get('altitude')} m")
    print(f"Battery:  {data.get('battery')} %")
    print(f"Location: {data.get('lat')}, {data.get('lon')}")
    
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000) #replace with nano address
