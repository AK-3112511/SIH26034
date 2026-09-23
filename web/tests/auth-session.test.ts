import { describe, expect, it } from "vitest";
import { isTokenExpired, readTokenExpiry } from "@/lib/auth-context";

/** Build a JWT-shaped string with the given payload. Signature is irrelevant here. */
function tokenWith(payload: Record<string, unknown>): string {
  const encode = (obj: unknown) =>
    Buffer.from(JSON.stringify(obj))
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${encode({ alg: "HS256", typ: "JWT" })}.${encode(payload)}.signature`;
}

describe("readTokenExpiry", () => {
  it("reads the exp claim", () => {
    expect(readTokenExpiry(tokenWith({ sub: "u1", exp: 1_800_000_000 }))).toBe(1_800_000_000);
  });

  it("returns null for a token with no exp", () => {
    expect(readTokenExpiry(tokenWith({ sub: "u1" }))).toBeNull();
  });

  it("returns null rather than throwing on a malformed token", () => {
    expect(readTokenExpiry("not-a-token")).toBeNull();
    expect(readTokenExpiry("a.b.c")).toBeNull();
    expect(readTokenExpiry("")).toBeNull();
  });
});

describe("isTokenExpired", () => {
  const now = Date.UTC(2026, 8, 23, 12, 0, 0);

  it("is true once exp has passed", () => {
    const token = tokenWith({ exp: Math.floor(now / 1000) - 60 });
    expect(isTokenExpired(token, now)).toBe(true);
  });

  it("is false while the token is still valid", () => {
    const token = tokenWith({ exp: Math.floor(now / 1000) + 3600 });
    expect(isTokenExpired(token, now)).toBe(false);
  });

  it("defers to the server when the token cannot be read", () => {
    // Refusing to sign in on an unreadable token would lock out an officer
    // over a client-side parsing quirk; the backend decides.
    expect(isTokenExpired("garbage", now)).toBe(false);
  });
});
