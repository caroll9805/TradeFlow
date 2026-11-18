import { Route, Routes } from "react-router-dom";
import AppLayout, { RequireAuth } from "@/components/Layout";
import Landing from "@/pages/Landing";
import { Login, Register } from "@/pages/Auth";
import Dashboard from "@/pages/Dashboard";
import Catalog from "@/pages/Catalog";
import ProductDetail from "@/pages/ProductDetail";
import Suppliers from "@/pages/Suppliers";
import SupplierProfile from "@/pages/SupplierProfile";
import Analytics from "@/pages/Analytics";
import RegionalAnalytics from "@/pages/RegionalAnalytics";
import Assistant from "@/pages/Assistant";
import Saved from "@/pages/Saved";
import Procurement from "@/pages/Procurement";
import SupplierDashboard from "@/pages/SupplierDashboard";
import MarketDataAdmin from "@/pages/admin/MarketDataAdmin";
import PlatformAdmin from "@/pages/admin/PlatformAdmin";
import SettingsPage from "@/pages/Settings";
import NotFound from "@/pages/NotFound";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<AppLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/catalog" element={<Catalog />} />
        <Route path="/products/:id" element={<ProductDetail />} />
        <Route path="/suppliers" element={<Suppliers />} />
        <Route path="/suppliers/:id" element={<SupplierProfile />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/regions" element={<RegionalAnalytics />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/saved" element={<RequireAuth><Saved /></RequireAuth>} />
        <Route path="/procurement" element={<RequireAuth perm="quotes.request"><Procurement /></RequireAuth>} />
        <Route path="/supplier" element={<RequireAuth perm="suppliers.manage_own"><SupplierDashboard /></RequireAuth>} />
        <Route path="/admin/market-data" element={<RequireAuth perm="market_data.manage"><MarketDataAdmin /></RequireAuth>} />
        <Route path="/admin/platform" element={<RequireAuth><PlatformAdmin /></RequireAuth>} />
        <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
