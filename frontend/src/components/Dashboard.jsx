import React, { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import "chart.js/auto";
import Select from "react-select"

const colors = ["#2563eb", "#16a34a", "#f59e0b", "#db2777", "#9333ea"];

export default function InsightDashboard() {
  const [devices, setDevices] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [trustHistory, setTrustHistory] = useState({});
  const [coordinator, setCoordinator] = useState(null);
  const [suspicious, setSuspicious] = useState([]);

  useEffect(() => {
    fetchDevices();
    fetchCoordinator();
  }, []);

  const fetchDevices = async () => {
    const res = await fetch("http://localhost:8000/devices");
    const data = await res.json();
    setDevices(data);
    const bad = data.filter(d => d.trust_score < 0.3);
    setSuspicious(bad);
  };

  const fetchCoordinator = async () => {
    const res = await fetch("http://localhost:8000/coordinator");
    const data = await res.json();
    setCoordinator(data);
  };

 const options = devices.map(d => ({ value: d.id, label: d.id }));

const handleMultiChange = async (selectedOptions) => {
  const selected = selectedOptions.map(o => o.value);
  setSelectedIds(selected);

  for (const id of selected) {
    if (!trustHistory[id]) {
      const res = await fetch(`http://localhost:8000/device/${id}/history`);
      const history = await res.json();
      setTrustHistory(prev => ({ ...prev, [id]: history }));
    }
  }
};

  const chartData = {
    labels: Array.from({ length: 20 }, (_, i) => i + 1),
    datasets: selectedIds.map((id, i) => ({
      label: id,
      data: trustHistory[id]?.map(h => h.trust_score) || [],
      borderColor: colors[i % colors.length],
      fill: false
    }))
  };

  return (
    <div className="container">
      <header className="card">
        <h1 className="text-xl">Insight Dashboard</h1>
        <p className="section-title">Real-time community status and trust analytics</p>
      </header>

      <div className="grid-3">
        <div className="card">
          <h2 className="section-title">Coordinator Device</h2>
          <p className="highlight-text">{coordinator?.name || "Loading..."}</p>
        </div>

        <div className={`card ${suspicious.length > 0 ? "alert-danger" : "alert-safe"}`}>
          <h2 className="section-title">Security Status</h2>
          <div>
            {suspicious.length > 0
              ? <ul>{suspicious.map(d => <li key={d.id}>⚠️ {d.id} ({d.trust_score.toFixed(2)})</li>)}</ul>
              : <p>Safe: No malicious activity detected.</p>}
          </div>
        </div>

        <div className="card">
          <h2 className="section-title">Select Device(s)</h2>
          <Select
            isMulti
            options={options}
            onChange={handleMultiChange}
            className="react-select-container"
            classNamePrefix="react-select"
            />
        </div>
      </div>

      <div className="card">
        <h2 className="section-title">Trust History Chart</h2>
        <Line data={chartData} />
        {selectedIds.map((id) => (
          <div key={id} className="card mt-4">
            <h2 className="section-title">Trust History: {id}</h2>
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Delta Direct</th>
                  <th>Indirect</th>
                  <th>Centrality</th>
                  <th>Updated Trust</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {trustHistory[id]?.map((entry, i) => (
                  <tr key={i}>
                    <td>{new Date(entry.timestamp).toLocaleString()}</td>
                    <td>{entry.direct_trust != null ? entry.direct_trust.toFixed(3) : "-"}</td>
                    <td>{entry.indirect_trust != null ? entry.indirect_trust.toFixed(3) : "-"}</td>
                    <td>{entry.centrality_score != null ? entry.centrality_score.toFixed(3) : "-"}</td>
                    <td>{entry.trust_score?.toFixed(3)}</td>
                    <td>{entry.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
