import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewForm } from "@/app/queue/[id]/components/ReviewForm";
import type { ChallanResponse, RuleResult, ScanStatus } from "@/lib/api";

const passing: RuleResult[] = [
  { id: "r1", rule_id: "6.1.a", status: "PASS", reason: null, evidence: null },
  { id: "r2", rule_id: "6.1.c", status: "PASS", reason: null, evidence: null },
];

const failing: RuleResult[] = [
  { id: "r1", rule_id: "6.1.a", status: "PASS", reason: null, evidence: null },
  {
    id: "r2",
    rule_id: "6.1.e",
    status: "FAIL",
    reason: "No 'inclusive of all taxes' near the price.",
    evidence: null,
  },
];

function setup(
  overrides: Partial<React.ComponentProps<typeof ReviewForm>> = {}
): { onSubmit: ReturnType<typeof vi.fn>; onGenerateChallan: ReturnType<typeof vi.fn> } {
  const onSubmit = vi.fn();
  const onGenerateChallan = vi.fn();
  render(
    <ReviewForm
      ruleResults={passing}
      scanStatus={"PENDING_REVIEW" as ScanStatus}
      existingNote={null}
      overrideCount={0}
      submitting={false}
      submitError={null}
      submitSuccess={null}
      onSubmit={onSubmit}
      existingChallan={null}
      generatingChallan={false}
      challanError={null}
      onGenerateChallan={onGenerateChallan}
      {...overrides}
    />
  );
  return { onSubmit, onGenerateChallan };
}

describe("ReviewForm", () => {
  it("defaults the verdict to what the engine found", () => {
    setup({ ruleResults: failing });
    expect(screen.getByLabelText(/verdict/i)).toHaveValue("FAILED");
    expect(screen.getByText(/rule 6\(1\)\(e\)/i)).toBeInTheDocument();
  });

  it("defaults to compliant only when nothing is in breach", () => {
    setup();
    expect(screen.getByLabelText(/verdict/i)).toHaveValue("PASSED");
  });

  it("refuses to submit without a reason", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup();

    expect(screen.getByRole("button", { name: /record verdict/i })).toBeDisabled();

    await user.type(screen.getByLabelText(/reason for the decision/i), "Checked by hand.");
    expect(screen.getByRole("button", { name: /record verdict/i })).toBeEnabled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("asks for confirmation before recording a verdict", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup();

    await user.type(screen.getByLabelText(/reason for the decision/i), "Declarations verified.");
    await user.click(screen.getByRole("button", { name: /record verdict/i }));

    // The decision is not sent on the first click any more.
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /confirm verdict/i }));
    expect(onSubmit).toHaveBeenCalledWith("PASSED", "Declarations verified.");
  });

  it("warns when a reviewer clears a scan the engine found in breach", async () => {
    const user = userEvent.setup();
    setup({ ruleResults: failing });

    await user.selectOptions(screen.getByLabelText(/verdict/i), "PASSED");
    await user.type(screen.getByLabelText(/reason for the decision/i), "Label reprinted on site.");
    await user.click(screen.getByRole("button", { name: /record verdict/i }));

    expect(screen.getByText(/you are clearing a scan/i)).toBeInTheDocument();
  });

  it("only offers a notice once the scan is recorded as not compliant", () => {
    setup({ scanStatus: "PENDING_REVIEW" as ScanStatus });
    expect(screen.getByRole("button", { name: /issue section 39 notice/i })).toBeDisabled();
  });

  it("enables the notice for a failed scan and confirms first", async () => {
    const user = userEvent.setup();
    const { onGenerateChallan } = setup({ scanStatus: "FAILED" as ScanStatus, ruleResults: failing });

    await user.click(screen.getByRole("button", { name: /issue section 39 notice/i }));
    expect(onGenerateChallan).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /^issue notice$/i }));
    expect(onGenerateChallan).toHaveBeenCalled();
  });

  it("shows the notice already issued instead of offering to issue another", () => {
    const challan: ChallanResponse = {
      challan_id: "c1",
      scan_id: "s1",
      lmo_id: "u1",
      pdf_url: "/api/v1/files/challan.pdf",
      pdf_hash: "abc123",
      generated_at: "2026-09-22T10:00:00Z",
    };
    setup({ scanStatus: "FAILED" as ScanStatus, existingChallan: challan });

    expect(screen.getByRole("link", { name: /open the notice/i })).toHaveAttribute(
      "href",
      "/api/v1/files/challan.pdf"
    );
    expect(
      screen.queryByRole("button", { name: /issue section 39 notice/i })
    ).not.toBeInTheDocument();
  });
});
