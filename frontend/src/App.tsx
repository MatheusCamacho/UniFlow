import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { LoginPage } from "./features/auth/LoginPage";
import { CalendarPage } from "./features/calendar/CalendarPage";
import { DashboardPage } from "./features/dashboard/DashboardPage";
import { NotificationsPage } from "./features/notifications/NotificationsPage";
import { IntegrationsPage } from "./features/settings/IntegrationsPage";
import { SubjectsPage } from "./features/subjects/SubjectsPage";
import { TasksPage } from "./features/tasks/TasksPage";
import { apiFetch, setCsrfToken } from "./lib/api";
import { User } from "./types";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<{ user: User; csrf_token: string }>("/auth/me")
      .then((res) => {
        setCsrfToken(res.csrf_token);
        setUser(res.user);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    await apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    setCsrfToken("");
    setUser(null);
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-paper text-sm text-muted">
        Carregando UniFlow...
      </div>
    );
  }

  if (!user) {
    return <LoginPage onSuccess={setUser} />;
  }

  return (
    <BrowserRouter>
      <Layout user={user} onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={<DashboardPage user={user} />} />
          <Route path="/tasks" element={<TasksPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/subjects" element={<SubjectsPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
