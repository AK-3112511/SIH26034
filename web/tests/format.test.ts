import { afterEach, describe, expect, it, vi } from "vitest";
import { formatCoords, formatDate, formatDateTime, shortId, timeAgo } from "@/lib/format";

afterEach(() => vi.useRealTimers());

describe("timeAgo", () => {
  it("describes recent, hourly and daily ages", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-23T12:00:00Z"));

    expect(timeAgo("2026-09-23T11:59:30Z")).toBe("just now");
    expect(timeAgo("2026-09-23T11:45:00Z")).toBe("15m ago");
    expect(timeAgo("2026-09-23T09:00:00Z")).toBe("3h ago");
    expect(timeAgo("2026-09-21T12:00:00Z")).toBe("2d ago");
  });

  it("does not report a negative age for a clock skewed ahead", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-23T12:00:00Z"));
    expect(timeAgo("2026-09-23T12:05:00Z")).toBe("just now");
  });

  it("returns a dash rather than 'Invalid Date' for missing input", () => {
    expect(timeAgo(null)).toBe("—");
    expect(timeAgo("not a date")).toBe("—");
  });
});

describe("shortId", () => {
  it("shortens a full identifier", () => {
    expect(shortId("3fa85f64-5717-4562-b3fc-2c963f66afa6")).toBe("3fa85f64");
  });

  it("does not throw on an id shorter than the cut", () => {
    expect(shortId("abc")).toBe("abc");
    expect(shortId("")).toBe("—");
    expect(shortId(null)).toBe("—");
  });
});

describe("formatDate and formatDateTime", () => {
  it("returns a dash for missing or unparseable values", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDateTime("nonsense")).toBe("—");
  });

  it("formats a real timestamp", () => {
    expect(formatDate("2026-09-23T12:00:00Z")).toMatch(/2026/);
  });
});

describe("formatCoords", () => {
  it("shows five decimal places, which is metres-level precision", () => {
    expect(formatCoords(13.0827, 80.2707)).toBe("13.08270, 80.27070");
  });

  it("says nothing rather than 0,0 when a scan has no location", () => {
    expect(formatCoords(null, null)).toBe("—");
  });
});
