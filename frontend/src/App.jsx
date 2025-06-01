import React, { useState } from "react";
import InsightDashboard from "./components/Dashboard";
import DevicePage from "./components/Device";
import LogActivityPage from "./components/LogActivity";

export default function App() {
  const [page, setPage] = useState("dashboard");

  const renderPage = () => {
    switch (page) {
      case "devices":
        return <DevicePage />;
      case "logs":
        return <LogActivityPage />;
      default:
        return <InsightDashboard />;
    }
  };

  return (
    <div>
      <nav className="navbar">
        <button
          onClick={() => setPage("dashboard")}
          className={`nav-button ${page === "dashboard" ? "active" : ""}`}
        >Insight</button>
        <button
          onClick={() => setPage("devices")}
          className={`nav-button ${page === "devices" ? "active" : ""}`}
        >Devices</button>
        <button
          onClick={() => setPage("logs")}
          className={`nav-button ${page === "logs" ? "active" : ""}`}
        >Logs</button>
      </nav>
      {renderPage()}
    </div>
  );
}
