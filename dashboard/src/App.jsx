import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import { ToastContainer } from './components/Toast';
import Overview from './pages/Overview';
import Agents from './pages/Agents';
import AuditLog from './pages/AuditLog';
import PolicyEditor from './pages/PolicyEditor';
import Costs from './pages/Costs';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="agents" element={<Agents />} />
          <Route path="audit" element={<AuditLog />} />
          <Route path="policy" element={<PolicyEditor />} />
          <Route path="costs" element={<Costs />} />
        </Route>
      </Routes>
      <ToastContainer />
    </BrowserRouter>
  );
}
