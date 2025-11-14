import React, { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function App() {
  const [pos, setPos] = useState({ x: 0, y: 0, z: 0 });
  const [chartData, setChartData] = useState([]);
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8765");

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      // update drone position
      setPos({
        x: data.x * 30,
        y: data.y * 30,
        z: data.z,
      });

      // update altitude chart
      setChartData((prev) => [
        ...prev.slice(-100),
        { time: Date.now(), altitude: data.z },
      ]);
    };

    return () => ws.close();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("User input submitted:", inputValue);
  };

  return (
    <div className="w-full min-h-screen bg-gray-950 text-white p-6 space-y-6">
      {/* Top Input Form */}
      <form onSubmit={handleSubmit} className="w-full flex gap-3">
        <input
          className="flex-1 p-3 rounded-lg bg-gray-800 border border-gray-700"
          placeholder="Enter simulation parameters..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
        />
        <button className="px-6 py-3 bg-blue-600 rounded-lg hover:bg-blue-700">
          Submit
        </button>
      </form>

      {/* Drone Visualizer */}
      <div className="w-full h-[300px] relative bg-gray-900 rounded-xl overflow-hidden">
        <div
          className="absolute w-6 h-6 bg-yellow-400 rounded-full shadow-lg"
          style={{
            left: `${pos.x}px`,
            top: `${pos.y}px`,
            transform: "translate(-50%, -50%)",
          }}
        />
      </div>

      {/* Altitude Chart */}
      <div className="w-full h-[250px] bg-gray-900 p-4 rounded-xl">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <XAxis dataKey="time" tick={false} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="altitude" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
