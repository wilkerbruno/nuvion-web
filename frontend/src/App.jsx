// frontend/src/App.jsx
import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Toaster } from "react-hot-toast";

import { useAuthStore, useNotifStore } from "./stores";
import Layout from "./components/layout/Layout";
import LoginPage from "./components/pages/LoginPage";
import RegisterPage from "./components/pages/RegisterPage";
import PanelPage from "./components/pages/PanelPage";
import PaymentPage from "./components/pages/PaymentPage";
import SettingsPage from "./components/pages/SettingsPage";
import AdminPage from "./components/pages/AdminPage";
import NotFoundPage from "./components/pages/NotFoundPage";


function PrivateRoute({ children }) {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn());
  return isLoggedIn ? children : <Navigate to="/login" replace />;
}

function AdminRoute({ children }) {
  const isAdmin = useAuthStore((s) => s.isAdmin());
  return isAdmin ? children : <Navigate to="/panel" replace />;
}

function PublicRoute({ children }) {
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn());
  return isLoggedIn ? <Navigate to="/panel" replace /> : children;
}


export default function App() {
  const { fetchUnreadCount } = useNotifStore();
  const isLoggedIn = useAuthStore((s) => s.isLoggedIn());

  // Buscar notificações periodicamente
  useEffect(() => {
    if (!isLoggedIn) return;
    fetchUnreadCount();
    const id = setInterval(fetchUnreadCount, 60_000);
    return () => clearInterval(id);
  }, [isLoggedIn]);

  return (
    <BrowserRouter>
      <Toaster position="top-right" toastOptions={{ duration: 4000 }} />
      <Routes>
        {/* Público */}
        <Route path="/login"    element={<PublicRoute><LoginPage /></PublicRoute>} />
        <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

        {/* Privado — dentro do Layout */}
        <Route element={<PrivateRoute><Layout><Outlet /></Layout></PrivateRoute>}>
          <Route index element={<Navigate to="/panel" replace />} />
          <Route path="/panel"    element={<PanelPage />} />
          <Route path="/payment"  element={<PaymentPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/admin"    element={<AdminRoute><AdminPage /></AdminRoute>} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
