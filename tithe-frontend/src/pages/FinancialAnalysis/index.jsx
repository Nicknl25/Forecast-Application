import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import "./styles.css";

const FinancialAnalysis = () => {
  return (
    <div className="fa-grid">
      {/* Sidebar */}
      <aside className="fa-sidebar">
        <h2 className="fa-title">Financial Analysis</h2>
        <nav className="fa-links">
          <NavLink to="dashboard" activeclassname="active">Dashboard</NavLink>
          <NavLink to="sheets" activeclassname="active">Sheets</NavLink>
          <NavLink to="forecast-drivers" activeclassname="active">Forecast Drivers</NavLink>
        </nav>
      </aside>

      {/* Main content */}
      <main className="fa-main">
        <Outlet />
      </main>
    </div>
  );
};

export default FinancialAnalysis;
