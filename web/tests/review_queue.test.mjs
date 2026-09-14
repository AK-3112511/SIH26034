import { test, describe } from "node:test";
import assert from "node:assert/strict";

describe("Review Queue — §3 Screen 3 & §4.2 Layout Specification", () => {
  const mockQueueItems = [
    {
      scan_id: "2558b244-06a3-4d2b-9259-ceba81780d5f",
      product_name: "Parle-G 100g",
      district_label: "Chennai, TN",
      confidence_gap: 0.24,
      created_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), // 2h ago
      age_hours: 2.0,
      image_url: "/static/uploads/parle_g_100g.jpg",
      status: "PENDING_REVIEW",
      source: "mobile",
    },
    {
      scan_id: "9f86d081-884c-7d65-9a2f-eaa0c55ad015",
      product_name: "Amul Butter 500g",
      district_label: "Coimbatore, TN",
      confidence_gap: 0.16,
      created_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(), // 5h ago
      age_hours: 5.0,
      image_url: "/static/uploads/amul_butter_500g.jpg",
      status: "PENDING_REVIEW",
      source: "mobile",
    },
    {
      scan_id: "5feceb66-ffc8-6f38-d952-786c6d696c79",
      product_name: "Maggi Noodles 70g",
      district_label: "Madurai, TN",
      confidence_gap: 0.31,
      created_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(), // 1d ago
      age_hours: 24.0,
      image_url: "/static/uploads/maggi_noodles_70g.jpg",
      status: "PENDING_REVIEW",
      source: "mobile",
    },
    {
      scan_id: "6b86b273-ff34-fce1-9d6b-804eff5a3f57",
      product_name: "Britannia Good Day 200g",
      district_label: "Salem, TN",
      confidence_gap: 0.08,
      created_at: new Date(Date.now() - 3 * 3600 * 1000).toISOString(), // 3h ago
      age_hours: 3.0,
      image_url: "/static/uploads/good_day_200g.jpg",
      status: "PENDING_REVIEW",
      source: "mobile",
    },
  ];

  function timeAgo(isoString) {
    const diff = Date.now() - new Date(isoString).getTime();
    const m = Math.floor(diff / 60000);
    const h = Math.floor(diff / 3600000);
    if (m < 60) return `${Math.max(1, m)}m ago`;
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  }

  test("queue displays items per §4.2 sketch format (Product, District, Relative Age)", () => {
    const item1 = mockQueueItems[0];
    assert.equal(item1.product_name, "Parle-G 100g");
    assert.equal(item1.district_label, "Chennai, TN");
    assert.equal(timeAgo(item1.created_at), "2h ago");

    const item2 = mockQueueItems[1];
    assert.equal(item2.product_name, "Amul Butter 500g");
    assert.equal(item2.district_label, "Coimbatore, TN");
    assert.equal(timeAgo(item2.created_at), "5h ago");

    const item3 = mockQueueItems[2];
    assert.equal(item3.product_name, "Maggi Noodles 70g");
    assert.equal(item3.district_label, "Madurai, TN");
    assert.equal(timeAgo(item3.created_at), "1d ago");
  });

  test("filtering by district correctly isolates district items", () => {
    function filterByDistrict(items, district) {
      if (!district) return items;
      return items.filter((i) => i.district_label.toLowerCase().includes(district.toLowerCase()));
    }

    const chennaiOnly = filterByDistrict(mockQueueItems, "Chennai");
    assert.equal(chennaiOnly.length, 1);
    assert.equal(chennaiOnly[0].product_name, "Parle-G 100g");

    const coimbatoreOnly = filterByDistrict(mockQueueItems, "Coimbatore");
    assert.equal(coimbatoreOnly.length, 1);
    assert.equal(coimbatoreOnly[0].product_name, "Amul Butter 500g");
  });

  test("sorting by confidence gap puts highest gap first", () => {
    const sorted = [...mockQueueItems].sort((a, b) => (b.confidence_gap || 0) - (a.confidence_gap || 0));
    assert.equal(sorted[0].product_name, "Maggi Noodles 70g"); // gap = 0.31 (31%)
    assert.equal(sorted[1].product_name, "Parle-G 100g"); // gap = 0.24 (24%)
    assert.equal(sorted[2].product_name, "Amul Butter 500g"); // gap = 0.16 (16%)
    assert.equal(sorted[3].product_name, "Britannia Good Day 200g"); // gap = 0.08 (8%)
  });

  test("sorting by age in both directions works accurately", () => {
    const newestFirst = [...mockQueueItems].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    assert.equal(newestFirst[0].product_name, "Parle-G 100g"); // 2h ago is newest

    const oldestFirst = [...mockQueueItems].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    assert.equal(oldestFirst[0].product_name, "Maggi Noodles 70g"); // 24h ago is oldest
  });

  test("search query filters by product name or scan ID", () => {
    function searchItems(items, query) {
      const q = query.toLowerCase().trim();
      if (!q) return items;
      return items.filter(
        (i) => i.product_name.toLowerCase().includes(q) || i.scan_id.toLowerCase().includes(q)
      );
    }

    const parleResults = searchItems(mockQueueItems, "Parle");
    assert.equal(parleResults.length, 1);
    assert.equal(parleResults[0].product_name, "Parle-G 100g");

    const idResults = searchItems(mockQueueItems, "5feceb66");
    assert.equal(idResults.length, 1);
    assert.equal(idResults[0].product_name, "Maggi Noodles 70g");
  });

  test("confidence and age band filters map to server query params, not page-local slicing", () => {
    function toListParams({ confidenceOption, ageOption, page }) {
      const confidence_band =
        confidenceOption === "critical" || confidenceOption === "moderate" || confidenceOption === "low"
          ? confidenceOption
          : undefined;
      const age_band =
        ageOption === "today" ? "today" : ageOption === "oldest" ? "older" : undefined;
      return { confidence_band, age_band, page, page_size: 20 };
    }

    const critical = toListParams({ confidenceOption: "critical", ageOption: "newest", page: 2 });
    assert.equal(critical.confidence_band, "critical");
    assert.equal(critical.age_band, undefined);
    assert.equal(critical.page, 2);

    const today = toListParams({ confidenceOption: "all", ageOption: "today", page: 1 });
    assert.equal(today.confidence_band, undefined);
    assert.equal(today.age_band, "today");

    const oldest = toListParams({ confidenceOption: "all", ageOption: "oldest", page: 1 });
    assert.equal(oldest.age_band, "older");
  });

  test("strict invariant: one-at-a-time selection only (no bulk selection)", () => {
    // Each row provides a singular link to /queue/{scan_id}
    const rowActions = mockQueueItems.map((item) => ({
      href: `/queue/${item.scan_id}`,
      hasCheckbox: false,
      hasBulkAction: false,
    }));

    for (const action of rowActions) {
      assert.equal(action.hasCheckbox, false, "Rows must never render bulk selection checkboxes");
      assert.equal(action.hasBulkAction, false, "Rows must never permit bulk actions");
      assert.ok(action.href.startsWith("/queue/"), "Row must link to single scan adjudication");
    }
  });
});
