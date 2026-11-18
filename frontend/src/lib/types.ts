export type Num = number | string | null;

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface Region { id: number; code: string; name_uz: string; name_ru: string; name_en: string;
  aliases: string[]; center_lat: Num; center_lng: Num; sort_order: number }

export interface Unit { id: number; code: string; name_uz: string; name_ru: string; name_en: string; symbol: string;
  dimension: string; factor_to_base: Num; aliases: string[] }

export interface AttributeOption { id: number; value: string; label_uz: string; label_ru: string; sort_order: number }
export interface CategoryAttribute { id: number; category_id: number; code: string; name_uz: string; name_ru: string;
  name_en: string | null; data_type: "text" | "number" | "boolean" | "date" | "select" | "multiselect";
  unit_id: number | null; is_required: boolean; is_filterable: boolean; is_matching_key: boolean; sort_order: number;
  options: AttributeOption[] }
export interface Category { id: number; parent_id: number | null; slug: string; name_uz: string; name_ru: string;
  name_en: string | null; description: string | null; icon: string | null; keywords: string[]; is_active: boolean;
  requires_compliance_note: boolean; compliance_note: string | null; freshness_hours: number | null; sort_order: number;
  attributes?: CategoryAttribute[] }

export interface OfferStats { offers: number; min_per_base_unit_uzs: Num; max_per_base_unit_uzs: Num;
  avg_per_base_unit_uzs: Num; regions: number; last_updated: string | null }
export interface Product { id: number; name: string; description: string | null; category_id: number;
  category: { id: number; slug: string; name_uz: string; name_ru: string } | null; brand: string | null; model: string | null;
  manufacturer_id: number | null; manufacturer: string | null; sku: string | null; barcode: string | null; base_unit: Unit;
  country_of_origin: string | null; origin_type: string; status: string; search_terms: string[]; is_simulated: boolean;
  attributes: { attribute_id: number; value: unknown }[]; images: string[]; created_at: string; updated_at: string;
  offer_stats?: OfferStats }

export interface SupplierLite { id: number; name: string; supplier_type: string; region: Region | null;
  verification_status: string; verified_at: string | null; rating_avg: Num; rating_count: number; is_simulated: boolean;
  organization_id: number | null; categories: { id: number; slug: string; name_uz: string; name_ru: string }[];
  description: string | null; website: string | null; is_active: boolean; active_offers?: number }
export interface SupplierDetail extends SupplierLite { legal_name: string | null; tin: string | null; phone: string | null;
  email: string | null; social_links: Record<string, string>; district_id: number | null; address: string | null; created_at: string;
  locations: { id: number; kind: string; name: string | null; region: Region; address: string | null; lat: Num; lng: Num }[];
  offers?: Offer[] }

export interface Offer { id: number; supplier: { id: number; name: string; verification_status: string; is_simulated: boolean };
  product: { id: number; name: string; category_id: number; base_unit: string }; original_price: Num;
  original_currency: string; exchange_rate: Num; exchange_rate_at: string | null; price_uzs: Num;
  price_per_base_unit_uzs: Num; unit: Unit; moq: Num; available_qty: Num; region: Region; delivery_available: boolean;
  delivery_cost_uzs: Num; delivery_regions: number[]; other_fees_uzs: Num; valid_from: string | null;
  valid_until: string | null; price_type: string; verification_status: string; provenance_kind: string;
  data_source: { id: number; name: string; code: string }; source_url: string | null; original_product_name: string | null;
  is_active: boolean; is_simulated: boolean; is_featured: boolean; price_updated_at: string }

export interface ScoreItem { criterion: string; score: number; weight: number; contribution: number }
export interface ComparedOffer { offer_id: number;
  supplier: { id: number; name: string; type: string; verification_status: string; rating_avg: Num; rating_count: number; is_simulated: boolean };
  region: { id: number; code: string; name_uz: string; name_ru: string };
  price: { original: Num; currency: string; unit: string; exchange_rate: Num; exchange_rate_at: string | null; price_uzs: Num;
    per_base_unit_uzs: Num; base_unit: string; price_type: string };
  moq: Num; available_qty: Num; available_base_units: Num; stock_status: string;
  delivery: { available: boolean; cost_uzs: Num; deliverable_to_buyer: boolean; cost_known: boolean; distance_km: number | null };
  cost: { order_units: Num; goods_uzs: Num; delivery_uzs: Num; fees_uzs: Num; total_uzs: Num; effective_per_base_unit_uzs: Num };
  freshness: { price_updated_at: string; age_hours: number; threshold_hours: number };
  provenance: { kind: string; source: string; source_id: number; source_url: string | null; verification_status: string;
    is_simulated: boolean; original_product_name: string | null };
  is_featured: boolean; notes: string[]; excluded_reason: string | null; score: number | null; score_breakdown: ScoreItem[];
  comparable_cost_uzs: Num; eligible_for_best: boolean }
export interface Comparison { product: { id: number; name: string; base_unit: string };
  weights: Record<string, number>; summary: { offers_total: number; offers_comparable: number; min_per_base_unit_uzs: Num;
    max_per_base_unit_uzs: Num; avg_per_base_unit_uzs: Num; base_unit: string; simulated_offers: number };
  cheapest_offer_id: number | null; best_offer_id: number | null; explanation: string[]; offers: ComparedOffer[] }

export interface RegionalPrice { region_id: number; code: string; name_uz: string; name_ru: string; center_lat: Num;
  center_lng: Num; offers: number; suppliers: number; min: Num; max: Num; avg: Num }
export interface HistoryPoint { period: string; avg: number; min: number; max: number; observations: number }
export interface History { status: string; granularity?: string; base_unit: string | null; points: HistoryPoint[];
  change_pct?: number | null; observations?: number; provenance_breakdown?: Record<string, number>;
  simulated_share?: number; first_observed_at?: string; last_observed_at?: string }
export interface Forecast { status: string; kind: string; method?: string; forecast?: { period: string; estimate: number; low: number; high: number }[];
  disclaimer?: string; required_weeks?: number; available_weeks?: number }
export interface Mover { product_id: number; name: string; base_unit: string; category_id: number; prev_avg: number;
  current_avg: number; change_pct: number; observations: number }
export interface Movers { status: string; window_days: number; threshold_pct: number; increases: Mover[]; decreases: Mover[]; method?: string }
export interface Overview { products_indexed: number; suppliers_registered: number; suppliers_verified: number;
  active_offers: number; simulated_active_offers: number; price_observations: number; last_collected_at: string | null;
  offers_by_category: { category_id: number; slug: string; name_uz: string; name_ru: string; offers: number }[] }
export interface RegionStat { region_id: number; code: string; name_uz: string; name_ru: string; name_en: string;
  center_lat: Num; center_lng: Num; active_offers: number; suppliers_with_offers: number; suppliers_registered: number }
export interface SourceFreshness { source_id: number; code: string; name: string; source_type: string; provenance: string;
  is_simulated: boolean; reliability_score: Num; freshness_hours: number; last_collected_at: string | null;
  observations: number; status: string }
export interface SupplyDemand { window_days: number; observed_supply: { active_offers: number; active_suppliers: number; regions: number };
  declared_stock_base_units: Num | "insufficient_data"; declared_stock_offers_reporting: number; search_interest: number;
  quote_requests: number; completed_transactions: number | "insufficient_data"; estimated_demand: "insufficient_data"; note: string }

export interface Observation { id: number; product_id: number; product_name: string | null; supplier_id: number | null;
  supplier_name: string | null; offer_id: number | null; original_product_name: string | null; original_price: Num;
  original_currency: string; original_unit_text: string | null; unit: string | null; exchange_rate: Num; price_uzs: Num;
  normalized_price_uzs: Num; region: Region; price_type: string; provenance_kind: string;
  data_source: { id: number; name: string } | null; collection_method: string; collection_job_id: number | null;
  source_url: string | null; observed_at: string; collected_at: string; verification_status: string; quality_score: Num;
  confidence: Num; quality_flags: string[]; is_outlier: boolean; is_simulated: boolean }

export interface User { id: number; email: string; full_name: string; phone: string | null; locale: string; is_active: boolean;
  role: string; role_name: { uz: string; ru: string } | null; permissions: string[]; created_at: string;
  last_login_at: string | null; organizations: { id: number; name: string; org_type: string; member_role: string }[] }

export interface AssistantAnswer { question: string; answer: string; mode: "llm" | "deterministic"; note: string | null;
  language: string; intent: string; tool: string | null; data: unknown;
  entities: { product: { id: number; name: string } | null; alternatives: { id: number; name: string }[];
    category: { id: number; slug: string } | null; regions: { id: number; code: string; name_uz: string; name_ru: string }[];
    quantity: Num; price_type: string | null };
  sources: { name: string; kind: string; is_simulated: boolean | null; latest?: string | null; offers?: number }[];
  disclaimers: string[] }

export interface Quote { id: number; status: string; product: { id: number; name: string }; supplier: { id: number; name: string };
  quantity: Num; unit_id: number; delivery_region_id: number | null; message: string | null; created_at: string;
  buyer_organization_id: number;
  responses: { id: number; price: Num; currency: string; unit_id: number; valid_until: string | null; message: string | null; created_at: string }[] }

export interface DataSource { id: number; code: string; name: string; source_type: string; default_provenance: string;
  base_url: string | null; terms_status: string; has_public_api: boolean | null; requires_auth: boolean | null;
  redistribution_allowed: boolean | null; price_kind: string | null; review_notes: string | null; reliability_score: Num;
  freshness_hours: number; is_active: boolean; is_simulated: boolean }
export interface Connector { id: number; data_source_id: number; data_source: string; name: string; connector_type: string;
  config: Record<string, unknown>; interval_minutes: number | null; is_enabled: boolean; last_run_at: string | null;
  last_success_at: string | null; last_failure_at: string | null; last_error: string | null;
  records_collected_total: number; records_rejected_total: number; status: string }
export interface Job { id: number; connector_id: number | null; data_source_id: number; data_source: string; trigger: string;
  status: string; started_at: string; finished_at: string | null; records_seen: number; records_collected: number;
  records_rejected: number; records_pending_review: number; records_duplicate: number; error: string | null; file_name: string | null }
export interface Match { id: number; original_name: string; score: Num; method: string; reasons: string[]; status: string;
  raw_record: Record<string, unknown>; created_at: string; data_source_id: number | null; candidate: Product | null }
