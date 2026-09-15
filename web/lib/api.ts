/**
 * Central API client for MetrologyAI web dashboard.
 * All requests go to the FastAPI backend via NEXT_PUBLIC_API_BASE_URL.
 * JWT token is read from localStorage and injected on every request.
 */
import axios from "axios";

// Browser calls same-origin /api/v1 (Next.js rewrites to FastAPI). Direct
// 127.0.0.1 fallback is for server-side / tests — avoid "localhost" which can
// resolve to IPv6 ::1 while uvicorn is bound only to 127.0.0.1.
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (typeof window === "undefined" ? "http://127.0.0.1:8000/api/v1" : "/api/v1");

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Inject JWT on every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("metrologyai_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// On 401, clear auth and redirect to login
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const url = String(error.config?.url ?? "");
    const isLogin = url.includes("/auth/login");
    if (error.response?.status === 401 && typeof window !== "undefined" && !isLogin) {
      localStorage.removeItem("metrologyai_token");
      localStorage.removeItem("metrologyai_user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: "field_lmo" | "senior_lmo" | "admin";
  district: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export const authApi = {
  login: (username: string, password: string) =>
    api.post<LoginResponse>("/auth/login", { username, password }),
  me: () => api.get<UserResponse>("/auth/me"),
};

// ─── Scans ────────────────────────────────────────────────────────────────────

export interface ExtractedField {
  id: string;
  field_name: string;
  raw_text: string | null;
  bbox: { x1: number; y1: number; x2: number; y2: number } | null;
  ocr_confidence: number | null;
  semantic_confidence: number | null;
  font_height_mm: number | null;
}

export interface RuleResult {
  id: string;
  rule_id: string;
  status: "PASS" | "FAIL" | "UNVERIFIED";
  reason: string | null;
  evidence: Record<string, unknown> | null;
}

export interface ScanDetail {
  scan_id: string;
  source: "mobile" | "ecommerce";
  status: "QUEUED" | "PASSED" | "FAILED" | "PENDING_REVIEW" | "CALIBRATION_FAILED";
  image_url: string;
  evidence_hash: string;
  lat: number | null;
  lng: number | null;
  captured_at_utc: string | null;
  mm_per_px: number | null;
  pdp_area_cm2: number | null;
  ruleset_version: string | null;
  created_at: string;
  extracted_fields: ExtractedField[];
  rule_results: RuleResult[];
  assigned_lmo_id: string | null;
  reviewer_note: string | null;
}

export interface ScanListItem {
  scan_id: string;
  source: string;
  status: string;
  image_url: string;
  lat: number | null;
  lng: number | null;
  captured_at_utc: string | null;
  created_at: string;
  product_name: string | null;
  district_label: string | null;
  confidence_gap: number | null;
  age_hours: number | null;
}

export interface ScanListResponse {
  items: ScanListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface DashboardStats {
  scanned_today: number;
  passed_today: number;
  failed_today: number;
  pending_review: number;
  calibration_failed_today: number;
}

export const scansApi = {
  stats: () => api.get<DashboardStats>("/scans/stats"),
  list: (params: {
    status?: string;
    district?: string;
    source?: string;
    q?: string;
    confidence_band?: "critical" | "moderate" | "low";
    age_band?: "today" | "older";
    sort_by?: string;
    sort_dir?: string;
    page?: number;
    page_size?: number;
  }) => api.get<ScanListResponse>("/scans/", { params }),
  detail: (scanId: string) => api.get<ScanDetail>(`/scans/${scanId}`),
  review: (
    scanId: string,
    body: { decision: string; reviewer_note: string; overridden_fields?: Record<string, string> }
  ) => api.post(`/scans/${scanId}/review`, body),
  ingestDerived: (formData: FormData) =>
    api.post<{ scan_id: string; status: string; message: string }>(
      "/scans/ingest-derived",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    ),
};

// ─── Challans ─────────────────────────────────────────────────────────────────

export interface ChallanResponse {
  challan_id: string;
  scan_id: string;
  lmo_id: string | null;
  pdf_url: string | null;
  pdf_hash: string | null;
  generated_at: string;
}

export interface ChallanListResponse {
  items: ChallanResponse[];
  total: number;
  page: number;
  page_size: number;
}

export const challansApi = {
  list: (params: { page?: number; page_size?: number }) =>
    api.get<ChallanListResponse>("/challans/", { params }),
  generate: (scan_id: string) =>
    api.post<ChallanResponse>("/challans/generate", { scan_id }),
};

// ─── Dashboard (§7.1 GIS heatmap) ──────────────────────────────────────────────

export interface HeatmapCluster {
  lat: number;
  lng: number;
  count: number;
  severity: "FAIL" | "PENDING" | "PASS";
  pass_count: number;
  fail_count: number;
  pending_count: number;
}

export interface HeatmapResponse {
  clusters: HeatmapCluster[];
  zoom: number;
  total_points: number;
}

export const dashboardApi = {
  /** Server-side PostGIS-clustered points — never raw unclustered scans. */
  heatmap: (params: { zoom?: number; bbox?: string }) =>
    api.get<HeatmapResponse>("/dashboard/heatmap", { params }),
};

// ─── Products (§10 Digital Repository / Product Search) ───────────────────────

export interface ProductScanEntry {
  scan_id: string;
  status: string;
  district_label: string | null;
  captured_at_utc: string | null;
  created_at: string;
  image_url: string;
}

export interface ProductSearchResult {
  manufacturer_name: string;
  total_scans: number;
  passed_count: number;
  failed_count: number;
  pending_review_count: number;
  other_count: number;
  pass_rate: number | null;
  trend: "IMPROVING" | "WORSENING" | "STABLE" | "INSUFFICIENT_DATA";
  first_scan_at: string;
  last_scan_at: string;
  scans: ProductScanEntry[];
}

export interface ProductSearchResponse {
  query: string | null;
  results: ProductSearchResult[];
  total: number;
  page: number;
  page_size: number;
}

export const productsApi = {
  search: (params: { q?: string; page?: number; page_size?: number }) =>
    api.get<ProductSearchResponse>("/products/search", { params }),
};

// ─── Admin: Ruleset Config (§3 Screen 8) ───────────────────────────────────────

export interface ScheduleIIBand {
  max_area_cm2: number | null;
  min_font_mm: number;
  description: string;
}

export interface RulesetVersion {
  version: string;
  effective_date: string;
  is_placeholder: boolean;
  notice: string;
  bands: ScheduleIIBand[];
  is_active: boolean;
  created_by_id: string | null;
  created_at: string;
}

export interface RulesetVersionListResponse {
  versions: RulesetVersion[];
}

export const adminRulesetsApi = {
  list: () => api.get<RulesetVersionListResponse>("/admin/rulesets"),
  create: (
    payload: {
      version: string;
      effective_date: string;
      is_placeholder: boolean;
      notice: string;
      bands: ScheduleIIBand[];
    },
    activate: boolean
  ) => api.post<RulesetVersion>("/admin/rulesets", payload, { params: { activate } }),
  activate: (version: string) =>
    api.post<RulesetVersion>(`/admin/rulesets/${encodeURIComponent(version)}/activate`),
};

// ─── Admin: User Management (§3 Screen 9) ──────────────────────────────────────

export interface UserListResponse {
  users: UserResponse[];
}

export const adminUsersApi = {
  list: () => api.get<UserListResponse>("/admin/users"),
  create: (payload: {
    username: string;
    email: string;
    password: string;
    full_name: string;
    role: "field_lmo" | "senior_lmo" | "admin";
    district?: string | null;
  }) => api.post<UserResponse>("/admin/users", payload),
  update: (
    userId: string,
    payload: { role?: string; district?: string | null; is_active?: boolean }
  ) => api.patch<UserResponse>(`/admin/users/${userId}`, payload),
};

// ─── Admin: Audit Log (§3 Screen 10) — read-only ───────────────────────────────

export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  actor_username: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  timestamp: string;
  detail: Record<string, unknown> | null;
}

export interface AuditLogListResponse {
  items: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

export const adminAuditLogApi = {
  list: (params: { target_type?: string; action?: string; page?: number; page_size?: number }) =>
    api.get<AuditLogListResponse>("/admin/audit-log", { params }),
};
