import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Company from './pages/Company';
import Methodology from './pages/Methodology';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/company/:companyName" element={<Company />} />
        <Route path="/companies/:companyName" element={<Company />} />
        <Route path="/company/:companyName/methodology" element={<Methodology />} />
        <Route path="/companies/:companyName/methodology" element={<Methodology />} />
      </Routes>
    </BrowserRouter>
  );
}