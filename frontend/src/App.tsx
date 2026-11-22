import { Link, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./features/auth/AuthProvider";
import { AppLayout, Wordmark } from "./layouts/AppLayout";
import { AboutPage } from "./pages/AboutPage";
import { CvsPage } from "./pages/CvsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { RegisterPage } from "./pages/RegisterPage";
import { TaxonomyPage } from "./pages/TaxonomyPage";

function ProtectedRoute() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <AppLayout /> : <Navigate to="/login" replace />;
}

/** About and Privacy: inside the app header when signed in, with a small public header otherwise. */
function OpenRoute() {
  const { isAuthenticated } = useAuth();
  if (isAuthenticated) return <AppLayout />;
  return (
    <div className="min-h-screen bg-mist">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-content items-center justify-between px-4 py-3 sm:px-8">
          <Link to="/login" aria-label="SkillGap sign in">
            <Wordmark />
          </Link>
          <Link className="btn-secondary" to="/login">Sign in</Link>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-content px-4 py-8 sm:px-8">
        <Outlet />
      </main>
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route element={<OpenRoute />}>
          <Route path="/about" element={<AboutPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<CvsPage />} />
          <Route path="/cvs" element={<Navigate to="/profile" replace />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/taxonomy" element={<TaxonomyPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
