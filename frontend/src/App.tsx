import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, useAuth } from "./features/auth/AuthProvider";
import { AppLayout } from "./layouts/AppLayout";
import { AboutPage } from "./pages/AboutPage";
import { DashboardPage } from "./pages/DashboardPage";
import { CvsPage } from "./pages/CvsPage";
import { JobsPage } from "./pages/JobsPage";
import { LoginPage } from "./pages/LoginPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { RegisterPage } from "./pages/RegisterPage";
import { TaxonomyPage } from "./pages/TaxonomyPage";
import { MatchingPage } from "./pages/MatchingPage";
import { MatchingFactsPage } from "./pages/MatchingFactsPage";
import { JobInventoryPage } from "./pages/JobInventoryPage";

function ProtectedRoute() {
  const { isAuthenticated, error, signOut } = useAuth();
  if (isAuthenticated && error) return <main className="mx-auto max-w-2xl p-6"><p role="alert">Unable to load your session: {error.message}</p><button type="button" className="mt-4 rounded border border-slate-300 px-4 py-2" onClick={signOut}>Return to sign in</button></main>;
  return isAuthenticated ? <AppLayout /> : <Navigate to="/login" replace />;
}

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/cvs" element={<CvsPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/matching" element={<MatchingPage />} />
          <Route path="/matching-facts" element={<MatchingFactsPage />} />
          <Route path="/job-inventories" element={<JobInventoryPage />} />
          <Route path="/job-inventories/:jobId" element={<JobInventoryPage />} />
          <Route path="/taxonomy" element={<TaxonomyPage />} />
        </Route>
      </Routes>
    </AuthProvider>
  );
}
