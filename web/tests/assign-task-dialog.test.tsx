import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AssignTaskDialog } from "@/app/queue/[id]/components/AssignTaskDialog";
import type { FieldOfficer } from "@/lib/api";

const officers: FieldOfficer[] = [
  {
    id: "officer-1",
    username: "a.iyer",
    email: "a.iyer@example.gov.in",
    full_name: "A Iyer",
    role: "field_lmo",
    district: "Coimbatore",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "officer-2",
    username: "s.rao",
    email: "s.rao@example.gov.in",
    full_name: "S Rao",
    role: "field_lmo",
    district: "Salem",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
  },
];

function setup(overrides: Partial<React.ComponentProps<typeof AssignTaskDialog>> = {}) {
  const onAssign = vi.fn();
  const onClose = vi.fn();
  const onRetryOfficers = vi.fn();
  render(
    <AssignTaskDialog
      open
      officers={officers}
      loadingOfficers={false}
      officersError={null}
      onRetryOfficers={onRetryOfficers}
      assigning={false}
      assignError={null}
      defaultInstructions="Verify the package on site."
      onAssign={onAssign}
      onClose={onClose}
      {...overrides}
    />
  );
  return { onAssign, onClose, onRetryOfficers };
}

describe("AssignTaskDialog", () => {
  it("renders as a real dialog on an opaque surface", () => {
    setup();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    // The panel used to be styled with tokens this project does not define,
    // which rendered it transparent.
    expect(dialog.querySelector(".bg-paper-000")).not.toBeNull();
  });

  it("lists only officers the server returned", async () => {
    setup();
    const select = screen.getByLabelText("Field officer") as HTMLSelectElement;
    expect(select.options).toHaveLength(2);
    expect(screen.getByRole("option", { name: /A Iyer/ })).toBeInTheDocument();
  });

  it("sends the chosen officer and the typed instructions", async () => {
    const user = userEvent.setup();
    const { onAssign } = setup();

    await user.selectOptions(screen.getByLabelText("Field officer"), "officer-2");

    const instructions = screen.getByLabelText(/instructions for the officer/i);
    await user.clear(instructions);
    await user.type(instructions, "Weigh three packets and serve notice.");

    await user.click(screen.getByTestId("confirm-assignment-button"));

    // The instructions were previously collected and then dropped.
    expect(onAssign).toHaveBeenCalledWith("officer-2", "Weigh three packets and serve notice.");
  });

  it("says the directory is empty instead of offering an invented officer", () => {
    setup({ officers: [] });

    expect(screen.getByText(/no active field officers are listed/i)).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Field officer" })).not.toBeInTheDocument();
    expect(screen.getByTestId("confirm-assignment-button")).toBeDisabled();
  });

  it("offers a retry when the directory could not be read", async () => {
    const user = userEvent.setup();
    const { onRetryOfficers } = setup({
      officers: [],
      officersError: "Could not reach the server.",
    });

    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetryOfficers).toHaveBeenCalled();
  });

  it("renders nothing when closed", () => {
    render(
      <AssignTaskDialog
        open={false}
        officers={officers}
        loadingOfficers={false}
        officersError={null}
        onRetryOfficers={vi.fn()}
        assigning={false}
        assignError={null}
        defaultInstructions=""
        onAssign={vi.fn()}
        onClose={vi.fn()}
      />
    );
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
