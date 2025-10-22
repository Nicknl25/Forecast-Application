import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Visibility log
console.log("API Base URL in use:", import.meta.env.VITE_API_BASE_URL);

// Lightweight helpers for existing imports
export const registerUser = (data) => api.post("/api/users/register", data);
export const loginUser = (data) => api.post("/api/users/login", data);
export const getCurrentUser = () => api.get("/api/users/me");
export const getQBAuthUrl = () => api.get("/api/qb/connect");

// Company / User Dashboard APIs
export const getCompanyInfo = () => api.get("/api/company/info");
export const getCompanyUsers = () => api.get("/api/company/users");
export const addCompanyUser = (payload) => api.post("/api/company/users", payload);
export const deleteCompanyUser = (userId) => api.delete(`/api/company/users/${userId}`);
export const updateCompanyUser = (userId, payload) => api.patch(`/api/company/users/${userId}`, payload);
export const updateCompanySettings = (payload) => api.patch("/api/company/settings", payload);
export const getAuditLog = (params = {}) => api.get("/api/company/audit-log", { params });

export default api;
