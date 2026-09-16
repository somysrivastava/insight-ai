import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './context/AuthContext'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { SignupPage } from './pages/SignupPage'
import { DatasetsListPage } from './pages/DatasetsListPage'
import { UploadPage } from './pages/UploadPage'
import { DatasetDetailPage } from './pages/DatasetDetailPage'
import { DashboardsPage } from './pages/DashboardsPage'
import { SchedulesPage } from './pages/SchedulesPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />

            <Route element={<ProtectedRoute />}>
              <Route path="/datasets" element={<DatasetsListPage />} />
              <Route path="/datasets/upload" element={<UploadPage />} />
              <Route path="/datasets/:id" element={<DatasetDetailPage />} />
              <Route path="/dashboards" element={<DashboardsPage />} />
              <Route path="/schedules" element={<SchedulesPage />} />
            </Route>

            <Route path="/" element={<Navigate to="/datasets" replace />} />
            <Route path="*" element={<Navigate to="/datasets" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
