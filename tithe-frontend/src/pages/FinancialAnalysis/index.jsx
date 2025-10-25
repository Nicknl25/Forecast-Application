import React from "react";
import { NavLink, Outlet } from "react-router-dom";
import Navbar from "../../components/Navbar.jsx";
import Footer from "../../components/Footer.jsx";
import "./styles.css";

const FinancialAnalysis = () => {
  return (
    <div className="fa-container">
      {/* Header */}
      <header className="fa-header">
        <Navbar />
      </header>

      {/* Sidebar */}
      <aside className="fa-sidebar">
        <h2 className="fa-title">Financial Analysis</h2>
        <nav className="fa-links">
          <NavLink to="dashboard" className={({ isActive }) => (isActive ? "active" : undefined)}>Dashboard</NavLink>
          <NavLink to="sheets" className={({ isActive }) => (isActive ? "active" : undefined)}>Sheets</NavLink>
          <NavLink to="forecast-drivers" className={({ isActive }) => (isActive ? "active" : undefined)}>Forecast Drivers</NavLink>
        </nav>
      </aside>

      {/* Main content */}
      <main className="fa-main">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="fa-footer">
        <Footer />
      </footer>
    </div>
  );
};

export default FinancialAnalysis;

