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

export default api;
