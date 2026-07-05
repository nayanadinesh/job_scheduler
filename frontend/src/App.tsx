import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Navigate, Route, BrowserRouter as Router, Routes } from 'react-router-dom';
import './App.css';
import { AppLayout } from './components/layout/AppLayout';
import { isAuthenticated } from './lib/auth';
import { JobsPage } from './pages/JobsPage';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { QueuesPage } from './pages/QueuesPage';
import { SubmitJobPage } from './pages/SubmitJobPage';
import { WorkersPage } from './pages/WorkersPage';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 2000 } },
});

function RequireAuth({ children }: { children: React.ReactNode }) {
  return isAuthenticated() ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
            <Route index element={<OverviewPage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="queues" element={<QueuesPage />} />
            <Route path="workers" element={<WorkersPage />} />
            <Route path="submit" element={<SubmitJobPage />} />
          </Route>
        </Routes>
      </Router>
    </QueryClientProvider>
  );
}
