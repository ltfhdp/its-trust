import React, { useEffect, useState } from "react";

export default function LogActivityPage() {
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    fetchLogs();
  }, []);

  const fetchLogs = async () => {
    const res = await fetch("http://localhost:8000/log_activity");
    const data = await res.json();
    setLogs(data);
  };

  return (
    <div className="container">
      <h1 className="text-xl">Log Aktivitas Perangkat</h1>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Device</th>
              <th>Activity</th>
              <th>Description</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={i} className={log.activity_type === "malicious" ? "danger" : ""}>
                <td>{new Date(log.timestamp).toLocaleString()}</td>
                <td className="text-blue">{log.device_id}</td>
                <td>{log.activity_type}</td>
                <td>{log.description}</td>
                <td>{log.connection_status || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
