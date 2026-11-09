import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { AppLayout } from "./components/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentDetailsPage } from "./pages/DocumentDetailsPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { EvaluationDetailPage } from "./pages/EvaluationDetailPage";
import { EvaluationsPage } from "./pages/EvaluationsPage";
import { TraceExplorerPage } from "./pages/TraceExplorerPage";
import { UploadPage } from "./pages/UploadPage";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/documents" element={<DocumentsPage />} />
              <Route path="/upload" element={<UploadPage />} />
              <Route path="/documents/:id" element={<DocumentDetailsPage />} />
              <Route
                path="/documents/:documentId/runs/:runId/trace"
                element={<TraceExplorerPage />}
              />
              <Route path="/evaluations" element={<EvaluationsPage />} />
              <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
