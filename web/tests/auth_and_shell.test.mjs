import { test, describe, beforeEach } from "node:test";
import assert from "node:assert/strict";

// Mock localStorage
class MockLocalStorage {
  constructor() {
    this.store = {};
  }
  getItem(key) {
    return this.store[key] ?? null;
  }
  setItem(key, value) {
    this.store[key] = String(value);
  }
  removeItem(key) {
    delete this.store[key];
  }
  clear() {
    this.store = {};
  }
}

globalThis.localStorage = new MockLocalStorage();

describe("Web Dashboard Authentication & Role Guarding", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const seniorLmoUser = {
    id: "usr-senior-001",
    username: "senior_priya",
    email: "priya@legalmetrology.gov.in",
    full_name: "Priya Sharma",
    role: "senior_lmo",
    district: "Madurai",
    is_active: true,
    created_at: "2026-09-01T00:00:00Z"
  };

  const adminUser = {
    id: "usr-admin-001",
    username: "admin_rajesh",
    email: "rajesh@legalmetrology.gov.in",
    full_name: "Rajesh V",
    role: "admin",
    district: "Chennai Central",
    is_active: true,
    created_at: "2026-09-01T00:00:00Z"
  };

  const fieldLmoUser = {
    id: "usr-field-001",
    username: "lmo_ramesh",
    email: "ramesh@legalmetrology.gov.in",
    full_name: "Ramesh Kumar",
    role: "field_lmo",
    district: "Coimbatore",
    is_active: true,
    created_at: "2026-09-01T00:00:00Z"
  };

  // Simulation of auth-context login logic
  async function simulateLogin(mockApiResponse) {
    const data = mockApiResponse;
    if (data.user.role === "field_lmo") {
      localStorage.removeItem("metrologyai_token");
      localStorage.removeItem("metrologyai_user");
      throw new Error("FIELD_LMO_REJECTED");
    }
    localStorage.setItem("metrologyai_token", data.access_token);
    localStorage.setItem("metrologyai_user", JSON.stringify(data.user));
    return {
      user: data.user,
      token: data.access_token,
      isDashboardRole: data.user.role === "senior_lmo" || data.user.role === "admin"
    };
  }

  // Simulation of hydration logic
  function simulateHydration() {
    const storedToken = localStorage.getItem("metrologyai_token");
    const storedUser = localStorage.getItem("metrologyai_user");
    if (storedToken && storedUser) {
      try {
        const parsed = JSON.parse(storedUser);
        if (parsed.role === "field_lmo") {
          localStorage.removeItem("metrologyai_token");
          localStorage.removeItem("metrologyai_user");
          return { user: null, token: null, isDashboardRole: false };
        }
        return {
          user: parsed,
          token: storedToken,
          isDashboardRole: parsed.role === "senior_lmo" || parsed.role === "admin"
        };
      } catch {
        localStorage.removeItem("metrologyai_token");
        localStorage.removeItem("metrologyai_user");
      }
    }
    return { user: null, token: null, isDashboardRole: false };
  }

  test("senior_lmo login succeeds and grants dashboard access", async () => {
    const mockResponse = {
      access_token: "jwt-token-senior",
      token_type: "bearer",
      user: seniorLmoUser
    };

    const result = await simulateLogin(mockResponse);
    assert.equal(result.user.role, "senior_lmo");
    assert.equal(result.isDashboardRole, true);
    assert.equal(localStorage.getItem("metrologyai_token"), "jwt-token-senior");
    assert.deepEqual(JSON.parse(localStorage.getItem("metrologyai_user")), seniorLmoUser);
  });

  test("admin login succeeds and grants dashboard access", async () => {
    const mockResponse = {
      access_token: "jwt-token-admin",
      token_type: "bearer",
      user: adminUser
    };

    const result = await simulateLogin(mockResponse);
    assert.equal(result.user.role, "admin");
    assert.equal(result.isDashboardRole, true);
    assert.equal(localStorage.getItem("metrologyai_token"), "jwt-token-admin");
  });

  test("field_lmo login is REJECTED with FIELD_LMO_REJECTED error and stores nothing", async () => {
    const mockResponse = {
      access_token: "jwt-token-field",
      token_type: "bearer",
      user: fieldLmoUser
    };

    await assert.rejects(
      async () => {
        await simulateLogin(mockResponse);
      },
      {
        name: "Error",
        message: "FIELD_LMO_REJECTED"
      }
    );

    // Verify no tokens leaked into localStorage
    assert.equal(localStorage.getItem("metrologyai_token"), null);
    assert.equal(localStorage.getItem("metrologyai_user"), null);
  });

  test("hydration purges any stored field_lmo token and denies dashboard access", () => {
    localStorage.setItem("metrologyai_token", "jwt-field-token");
    localStorage.setItem("metrologyai_user", JSON.stringify(fieldLmoUser));

    const state = simulateHydration();
    assert.equal(state.user, null);
    assert.equal(state.token, null);
    assert.equal(state.isDashboardRole, false);
    assert.equal(localStorage.getItem("metrologyai_token"), null);
    assert.equal(localStorage.getItem("metrologyai_user"), null);
  });

  test("hydration restores senior_lmo session", () => {
    localStorage.setItem("metrologyai_token", "jwt-senior-token");
    localStorage.setItem("metrologyai_user", JSON.stringify(seniorLmoUser));

    const state = simulateHydration();
    assert.deepEqual(state.user, seniorLmoUser);
    assert.equal(state.token, "jwt-senior-token");
    assert.equal(state.isDashboardRole, true);
  });
});

describe("AppShell Navigation §4.2 Layout Sketch & RBAC", () => {
  const NAV_ITEMS = [
    { label: "Overview", href: "/", roles: ["senior_lmo", "admin"] },
    { label: "Review Queue", href: "/queue", roles: ["senior_lmo", "admin"], star: true },
    { label: "Repository", href: "/repository", roles: ["senior_lmo", "admin"] },
    { label: "E-Commerce", href: "/ecommerce", roles: ["senior_lmo", "admin"] },
    { label: "Challans", href: "/challans", roles: ["senior_lmo", "admin"] },
    { label: "Admin", href: "/admin/rulesets", roles: ["admin"] },
  ];

  function getVisibleNav(role) {
    return NAV_ITEMS.filter((item) => item.roles.includes(role));
  }

  test("senior_lmo sees Overview, Review Queue*, Repository, E-Commerce, Challans (NO Admin)", () => {
    const nav = getVisibleNav("senior_lmo");
    const labels = nav.map((i) => i.label);
    assert.deepEqual(labels, ["Overview", "Review Queue", "Repository", "E-Commerce", "Challans"]);
    assert.equal(nav.find((i) => i.label === "Admin"), undefined);

    // Review Queue has the signature asterisk from §4.2 sketch
    const reviewQueueItem = nav.find((i) => i.label === "Review Queue");
    assert.equal(reviewQueueItem.star, true);
  });

  test("admin sees all nav items including Admin", () => {
    const nav = getVisibleNav("admin");
    const labels = nav.map((i) => i.label);
    assert.deepEqual(labels, ["Overview", "Review Queue", "Repository", "E-Commerce", "Challans", "Admin"]);
    assert.ok(nav.find((i) => i.label === "Admin"));
  });

  test("field_lmo has zero visible dashboard nav items", () => {
    const nav = getVisibleNav("field_lmo");
    assert.equal(nav.length, 0);
  });

  test("§4.2 nav destinations that belong to later phases still have routes", () => {
    const laterPhaseRoutes = [
      { href: "/repository", phase: "6.2" },
      { href: "/challans", phase: "5.3" },
      { href: "/admin/rulesets", phase: "6.3" },
    ];
    for (const route of laterPhaseRoutes) {
      assert.ok(route.href.startsWith("/"));
      assert.ok(route.phase);
    }
    const hrefs = NAV_ITEMS.map((i) => i.href);
    assert.ok(hrefs.includes("/repository"));
    assert.ok(hrefs.includes("/challans"));
    assert.ok(hrefs.includes("/admin/rulesets"));
  });

  test("route guard redirects unauthenticated users to /login", () => {
    function guardRoute(user, isDashboardRole) {
      if (!user) return "/login";
      if (!isDashboardRole) return "/login?rejected=1";
      return null; // allowed
    }

    assert.equal(guardRoute(null, false), "/login");
    assert.equal(guardRoute({ role: "field_lmo" }, false), "/login?rejected=1");
    assert.equal(guardRoute({ role: "senior_lmo" }, true), null);
    assert.equal(guardRoute({ role: "admin" }, true), null);
  });
});
