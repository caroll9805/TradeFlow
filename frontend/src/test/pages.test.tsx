import { describe, expect, it } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Login } from "@/pages/Auth";
import Catalog from "@/pages/Catalog";
import Dashboard from "@/pages/Dashboard";
import ProductDetail from "@/pages/ProductDetail";
import PlatformAdmin from "@/pages/admin/PlatformAdmin";
import { EmptyState, ErrorState } from "@/components/ui";
import { mockFetch, renderApp, USER } from "./utils";

const CATS = [
  { id: 1, slug: "food", name_uz: "Oziq-ovqat", name_ru: "Продукты", name_en: "Food & beverages", is_active: true, keywords: [], sort_order: 0, parent_id: null, description: null, icon: null, requires_compliance_note: false, compliance_note: null, freshness_hours: null },
  { id: 5, slug: "construction", name_uz: "Qurilish", name_ru: "Стройматериалы", name_en: "Construction materials", is_active: true, keywords: [], sort_order: 4, parent_id: null, description: null, icon: null, requires_compliance_note: false, compliance_note: null, freshness_hours: null },
];
const UNIT = { id: 2, code: "kg", name_uz: "kilogramm", name_ru: "килограмм", name_en: "kilogram", symbol: "kg", dimension: "mass", factor_to_base: 1, aliases: [] };
const PRODUCT = { id: 10, name: "Portland cement M400 50kg", description: null, category_id: 5, category: { id: 5, slug: "construction", name_uz: "Qurilish", name_ru: "Стройматериалы" },
  brand: null, model: null, manufacturer_id: null, manufacturer: null, sku: null, barcode: null, base_unit: UNIT, country_of_origin: "UZ", origin_type: "domestic",
  status: "active", search_terms: [], is_simulated: true, attributes: [], images: [], created_at: "2026-10-01T00:00:00Z", updated_at: "2026-10-01T00:00:00Z",
  offer_stats: { offers: 3, min_per_base_unit_uzs: 1420, max_per_base_unit_uzs: 1600, avg_per_base_unit_uzs: 1500, regions: 2, last_updated: "2026-11-16T10:00:00Z" } };

describe("shared states", () => {
  it("renders empty and error states", () => {
    mockFetch([]);
    renderApp(<><EmptyState title="Nothing" /><ErrorState error={new Error("Boom")} /></>);
    expect(screen.getByText("Nothing")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
  });
});

describe("authentication flow", () => {
  it("validates input, logs in and redirects", async () => {
    const calls = mockFetch([
      { method: "POST", match: /\/api\/auth\/login$/, body: { access_token: "a", refresh_token: "r" } },
      { match: /\/api\/auth\/me$/, body: USER },
    ]);
    renderApp(<Login />, { route: "/login", path: "/login" });
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Enter a valid email")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Email"), "buyer@x.uz");
    await userEvent.type(screen.getByLabelText("Password"), "Secret123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("DASHBOARD PAGE")).toBeInTheDocument();
    expect(localStorage.getItem("tf_access")).toBe("a");
    expect(JSON.parse(String(calls.find((c) => c.method === "POST")!.body))).toEqual({ email: "buyer@x.uz", password: "Secret123" });
  });

  it("shows the server error on bad credentials", async () => {
    mockFetch([{ method: "POST", match: /\/api\/auth\/login$/, status: 401, body: { detail: "Invalid email or password" } }]);
    renderApp(<Login />, { route: "/login", path: "/login" });
    await userEvent.type(screen.getByLabelText("Email"), "x@x.uz");
    await userEvent.type(screen.getByLabelText("Password"), "nope");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });
});

describe("catalog", () => {
  it("searches and filters by category through the API", async () => {
    const calls = mockFetch([
      { match: /\/api\/categories\?/, body: CATS },
      { match: /\/api\/categories\/5$/, body: { ...CATS[1], attributes: [] } },
      { match: /\/api\/regions$/, body: [] },
      { match: /\/api\/products\/brands/, body: [] },
      { match: /\/api\/products\?/, body: (url: string) => ({ items: url.includes("q=cement") || url.includes("category_id=5") ? [PRODUCT] : [], total: url.includes("q=cement") || url.includes("category_id=5") ? 1 : 0, page: 1, page_size: 20 }) },
    ]);
    renderApp(<Catalog />, { route: "/catalog", path: "/catalog" });
    expect(await screen.findByText("No products found")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: /Search by name/ }), "cement");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Portland cement M400 50kg")).toBeInTheDocument();
    expect(calls.some((c) => c.url.includes("/api/products?") && c.url.includes("q=cement"))).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Construction materials" }));
    await waitFor(() => expect(calls.some((c) => c.url.includes("category_id=5"))).toBe(true));
    expect(screen.getAllByText("SIMULATED").length).toBeGreaterThan(0);
  });

  it("shows an error state when the API fails", async () => {
    mockFetch([
      { match: /\/api\/categories/, body: CATS },
      { match: /\/api\/products\/brands/, body: [] },
      { match: /\/api\/products\?/, status: 500, body: { detail: "Internal server error" } },
    ]);
    renderApp(<Catalog />, { route: "/catalog", path: "/catalog" });
    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});

const offer = (id: number, name: string, perUnit: number, score: number | null, extra: Record<string, unknown> = {}) => ({
  offer_id: id, supplier: { id, name, type: "wholesaler", verification_status: id === 2 ? "verified" : "unverified", rating_avg: null, rating_count: 0, is_simulated: false },
  region: { id: 1, code: "UZ-TK", name_uz: "Toshkent shahri", name_ru: "г. Ташкент" },
  price: { original: perUnit * 50, currency: "UZS", unit: "bag", exchange_rate: null, exchange_rate_at: null, price_uzs: perUnit * 50, per_base_unit_uzs: perUnit, base_unit: "kg", price_type: "wholesale" },
  moq: 1, available_qty: 100, available_base_units: 5000, stock_status: "declared",
  delivery: { available: false, cost_uzs: null, deliverable_to_buyer: true, cost_known: true, distance_km: null },
  cost: { order_units: null, goods_uzs: null, delivery_uzs: null, fees_uzs: null, total_uzs: null, effective_per_base_unit_uzs: null },
  freshness: { price_updated_at: new Date().toISOString(), age_hours: 1, threshold_hours: 168 },
  provenance: { kind: "supplier_declared", source: "Supplier submissions (TradeFlow)", source_id: 1, source_url: null, verification_status: "unverified", is_simulated: false, original_product_name: "x" },
  is_featured: false, notes: [], excluded_reason: null, score,
  score_breakdown: [{ criterion: "price", score: 1, weight: 0.45, contribution: 0.45 }, { criterion: "reliability", score: 0.8, weight: 0.2, contribution: 0.16 }],
  comparable_cost_uzs: perUnit, eligible_for_best: true, ...extra });

describe("offer comparison", () => {
  it("highlights cheapest and best overall and sends quantity to the backend", async () => {
    const calls = mockFetch([
      { match: /\/api\/products\/10$/, body: PRODUCT },
      { match: /\/api\/categories\/5$/, body: { ...CATS[1], attributes: [] } },
      { match: /\/api\/regions$/, body: [] },
      { match: /\/api\/products\/10\/compare/, body: {
        product: { id: 10, name: PRODUCT.name, base_unit: "kg" }, weights: { price: 0.45, reliability: 0.2, freshness: 0.15, stock: 0.1, distance: 0.1 },
        summary: { offers_total: 2, offers_comparable: 2, min_per_base_unit_uzs: 1420, max_per_base_unit_uzs: 1500, avg_per_base_unit_uzs: 1460, base_unit: "kg", simulated_offers: 0 },
        cheapest_offer_id: 1, best_offer_id: 2, explanation: ["Cheapest is ranked by price per base unit."],
        offers: [offer(2, "Solid Verified", 1500, 0.9), offer(1, "Cheap Co", 1420, 0.7)] } },
      { match: /\/api\/products\/10\/regional/, body: [] },
      { match: /\/api\/products\/10\/supply-demand/, body: { window_days: 30, observed_supply: { active_offers: 2, active_suppliers: 2, regions: 1 }, declared_stock_base_units: 10000, declared_stock_offers_reporting: 2, search_interest: 4, quote_requests: 0, completed_transactions: "insufficient_data", estimated_demand: "insufficient_data", note: "" } },
      { match: /\/api\/products\/10\/history/, body: { status: "insufficient_data", points: [], base_unit: "kg" } },
      { match: /\/api\/products\/10\/observations/, body: { items: [], total: 0, page: 1, page_size: 10 } },
    ]);
    renderApp(<ProductDetail />, { route: "/products/10", path: "/products/:id" });
    expect(await screen.findByRole("heading", { name: PRODUCT.name })).toBeInTheDocument();
    const cheapestCard = (await screen.findAllByText("Cheapest"))[0].closest("div")!.parentElement!;
    expect(within(cheapestCard).getByText("Cheap Co")).toBeInTheDocument();
    expect(screen.getAllByText("Best overall").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Solid Verified").length).toBeGreaterThan(0);
    expect(screen.getByText("Cheapest is ranked by price per base unit.")).toBeInTheDocument();
    // demand is never invented
    expect(screen.getAllByText("Insufficient data").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Quantity needed (kg)"), { target: { value: "5000" } });
    await waitFor(() => expect(calls.some((c) => c.url.includes("/compare?") && c.url.includes("quantity=5000"))).toBe(true));
  });
});

describe("dashboard", () => {
  it("loads KPIs from the backend", async () => {
    mockFetch([
      { match: /\/api\/analytics\/overview/, body: { products_indexed: 42, suppliers_registered: 30, suppliers_verified: 0, active_offers: 180, simulated_active_offers: 180, price_observations: 1900, last_collected_at: null, offers_by_category: [] } },
      { match: /\/api\/analytics\/movers/, body: { status: "insufficient_data", window_days: 14, threshold_pct: 5, increases: [], decreases: [] } },
      { match: /\/api\/analytics\/regions/, body: [] },
      { match: /\/api\/analytics\/recent-offers/, body: [] },
      { match: /\/api\/analytics\/freshness/, body: [] },
      { match: /\/api\/categories/, body: CATS },
      { match: /\/api\/regions$/, body: [] },
    ]);
    renderApp(<Dashboard />, { route: "/dashboard-x", path: "/dashboard-x" });
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("180 simulated")).toBeInTheDocument();
    expect(screen.getAllByText("Insufficient data").length).toBe(2);
  });
});

describe("admin actions", () => {
  it("purges simulated data only after confirmation", async () => {
    localStorage.setItem("tf_access", "t");
    const calls = mockFetch([
      { match: /\/api\/auth\/me$/, body: { ...USER, role: "super_admin", permissions: ["demo.manage"] } },
      { match: /\/api\/admin\/demo-data$/, body: { products: 42, suppliers: 30, offers: 180, observations: 1900, manufacturers: 1, organizations: 33, data_sources: 1 } },
      { method: "DELETE", match: /\/api\/admin\/demo-data$/, body: { removed: {} } },
    ]);
    renderApp(<PlatformAdmin />, { route: "/admin", path: "/admin" });
    await userEvent.click(await screen.findByRole("button", { name: "Remove all simulated data" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("/api/admin/demo-data"))).toBe(true));
    expect(await screen.findByText("Simulated data removed.")).toBeInTheDocument();
  });
});
