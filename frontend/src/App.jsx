import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { MobileMenuProvider } from './contexts/MobileMenuContext';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Framework from './pages/Framework';
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

function CompanyRedirect() {
  // Redirect /company/:name to first product's tape overview
  // CompanyLayout will handle loading products and resolving the default
  return <Navigate to="tape/overview" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <MobileMenuProvider>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/framework" element={<Framework />} />

        {/* Company routes with sidebar layout */}
        <Route path="/company/:companyName/:product" element={<CompanyLayout />}>
          <Route index element={<Navigate to="tape/overview" replace />} />
          <Route path="tape" element={<Navigate to="overview" replace />} />
          <Route path="tape/:tab" element={<TapeAnalytics />} />
          <Route path="portfolio" element={<Navigate to="borrowing-base" replace />} />
          <Route path="portfolio/:tab" element={<PortfolioAnalytics />} />
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
      </MobileMenuProvider>
    </BrowserRouter>
  );
}
