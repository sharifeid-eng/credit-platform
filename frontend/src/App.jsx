import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect } from 'react';
import { MobileMenuProvider } from './contexts/MobileMenuContext';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Framework from './pages/Framework';
import Architecture from './pages/Architecture';
import CompanyLayout from './layouts/CompanyLayout';
import TapeAnalytics from './pages/TapeAnalytics';
import PortfolioAnalytics from './pages/PortfolioAnalytics';
import Methodology from './pages/Methodology';
import ExecutiveSummary from './pages/ExecutiveSummary';
import DocumentLibrary from './pages/research/DocumentLibrary';
import ResearchChat from './pages/research/ResearchChat';
import MemoArchive from './pages/research/MemoArchive';
import MemoBuilder from './pages/research/MemoBuilder';
import MemoEditor from './pages/research/MemoEditor';
import LegalAnalytics from './pages/LegalAnalytics';
import OperatorCenter from './pages/OperatorCenter';
import UserManagement from './pages/UserManagement';
import Onboarding from './pages/Onboarding';

function CompanyRedirect() {
  // Redirect /company/:name to first product's tape overview
  // CompanyLayout will handle loading products and resolving the default
  return <Navigate to="tape/overview" replace />
}

// React Router preserves scroll position across navigations by default —
// clicking a link from a scrolled page would land the new page mid-scroll.
// This component resets window scroll on every pathname change. Tabs that
// only swap a :tab URL param (same pathname) stay where they are.
function ScrollToTopOnNavigate() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <MobileMenuProvider>
      <ProtectedRoute>
      <ScrollToTopOnNavigate />
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/framework" element={<Framework />} />
        <Route path="/architecture" element={<Architecture />} />
        <Route path="/operator" element={<OperatorCenter />} />
        <Route path="/onboard" element={<Onboarding />} />
        <Route path="/admin/users" element={
          <ProtectedRoute requireAdmin><UserManagement /></ProtectedRoute>
        } />

        {/* Company routes with sidebar layout */}
        <Route path="/company/:companyName/:product" element={<CompanyLayout />}>
          <Route index element={<Navigate to="tape/overview" replace />} />
          <Route path="tape" element={<Navigate to="overview" replace />} />
          <Route path="tape/:tab" element={<TapeAnalytics />} />
          <Route path="portfolio" element={<Navigate to="borrowing-base" replace />} />
          <Route path="portfolio/:tab" element={<PortfolioAnalytics />} />
          <Route path="legal" element={<Navigate to="documents" replace />} />
          <Route path="legal/:tab" element={<LegalAnalytics />} />
          <Route path="executive-summary" element={<ExecutiveSummary />} />
          <Route path="research" element={<Navigate to="library" replace />} />
          <Route path="research/library" element={<DocumentLibrary />} />
          <Route path="research/chat" element={<ResearchChat />} />
          <Route path="research/memos" element={<MemoArchive />} />
          <Route path="research/memos/new" element={<MemoBuilder />} />
          <Route path="research/memos/:memoId" element={<MemoEditor />} />
          <Route path="methodology" element={<Methodology />} />
        </Route>

        {/* Legacy redirects: /company/:name without product */}
        <Route path="/company/:companyName" element={<CompanyLayout />}>
          <Route index element={<Navigate to="tape/overview" replace />} />
          <Route path="tape" element={<Navigate to="overview" replace />} />
          <Route path="tape/:tab" element={<TapeAnalytics />} />
          <Route path="portfolio" element={<Navigate to="borrowing-base" replace />} />
          <Route path="portfolio/:tab" element={<PortfolioAnalytics />} />
          <Route path="legal" element={<Navigate to="documents" replace />} />
          <Route path="legal/:tab" element={<LegalAnalytics />} />
          <Route path="executive-summary" element={<ExecutiveSummary />} />
          <Route path="research" element={<Navigate to="library" replace />} />
          <Route path="research/library" element={<DocumentLibrary />} />
          <Route path="research/chat" element={<ResearchChat />} />
          <Route path="research/memos" element={<MemoArchive />} />
          <Route path="research/memos/new" element={<MemoBuilder />} />
          <Route path="research/memos/:memoId" element={<MemoEditor />} />
          <Route path="methodology" element={<Methodology />} />
        </Route>

        {/* Legacy alias */}
        <Route path="/companies/:companyName/*" element={<Navigate to="/company/:companyName" replace />} />
      </Routes>
      </ProtectedRoute>
      </MobileMenuProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
