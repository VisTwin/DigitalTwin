from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/telemetry', methods=['POST'])
def telemetry():
    data = request.get_json({
  "altitude": [Extracted Altitude],
  "battery": [Battery Level],
  "lat": [Location Latitude],
  "lon": [Location Longitude]
})
    print("📡 Telemetry Received:")
    print(data)
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

