import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Company from './pages/Company';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/company/:companyName" element={<Company />} />
        <Route path="/companies/:companyName" element={<Company />} />
      </Routes>
    </BrowserRouter>
  );
}