import React, { useEffect, useState } from "react";

export default function DevicePage() {
  const [devices, setDevices] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    id: "",
    name: "",
    device_type: "",
    ownership_type: "",
    memory_gb: 1,
    location: ""
  });

  useEffect(() => {
    fetchDevices();
  }, []);

  const fetchDevices = async () => {
    const res = await fetch("http://localhost:8000/devices");
    const data = await res.json();
    setDevices(data);
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    await fetch("http://localhost:8000/device", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData)
    });
    setFormData({ id: "", name: "", device_type: "", ownership_type: "", memory_gb: 1, location: "" });
    fetchDevices();
    setShowForm(false);
  };

  return (
    <div className="container">
      <h1 className="text-xl">Devices</h1>

      <button onClick={() => setShowForm(!showForm)} className="submit-btn">
        {showForm ? "Sembunyikan Form" : "Tambah Device"}
      </button>

      {showForm && (
        <form className="card form-grid" onSubmit={handleSubmit}>
          <input name="id" value={formData.id} onChange={handleChange} placeholder="Device ID" required />
          <input name="name" value={formData.name} onChange={handleChange} placeholder="Device Name" required />
          <input name="device_type" value={formData.device_type} onChange={handleChange} placeholder="Device Type (e.g., RSU)" required />
          <input name="ownership_type" value={formData.ownership_type} onChange={handleChange} placeholder="Ownership Type" required />
          <input name="memory_gb" type="number" value={formData.memory_gb} onChange={handleChange} placeholder="Memory (GB)" required />
          <input name="location" value={formData.location} onChange={handleChange} placeholder="Location" required />
          <button type="submit" className="submit-btn">Add Device</button>
        </form>
      )}

      <div className="card">
        <h2 className="section-title">Device List</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Type</th>
              <th>Owner</th>
              <th>Trust</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {devices.map(d => (
              <tr key={d.id} className={d.trust_score < 0.3 ? "danger" : ""}>
                <td>{d.id}</td>
                <td>{d.name}</td>
                <td>{d.device_type}</td>
                <td>{d.ownership_type}</td>
                <td>{d.trust_score.toFixed(3)}</td>
                <td>{d.is_blacklisted ? "Blacklisted" : "Active"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
