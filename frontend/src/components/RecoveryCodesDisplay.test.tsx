// Integration test for RecoveryCodesDisplay (Task T5, FR-5's one-time
// display). PS-AC5: recovery codes are displayed exactly once, the flow
// cannot complete until the user explicitly confirms they saved them, and
// the codes are never written to any storage API, the console, or a
// third-party request. Copy uses `navigator.clipboard`, download builds a
// local Blob/object-URL — neither touches the network.
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RecoveryCodesDisplay } from "./RecoveryCodesDisplay";

const codes = ["AAAA-1111", "BBBB-2222", "CCCC-3333"];

describe("RecoveryCodesDisplay", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("test_recovery_codes_display_renders_every_code_in_a_keyboard_selectable_list", () => {
    // Arrange / Act
    render(<RecoveryCodesDisplay codes={codes} onConfirmed={() => {}} />);

    // Assert
    for (const code of codes) {
      expect(screen.getByText(code)).toBeInTheDocument();
    }
  });

  it("test_recovery_codes_display_copy_control_writes_codes_to_the_clipboard_api", async () => {
    // Arrange
    // @testing-library/user-event@14's userEvent.setup() unconditionally
    // installs its own getter-only navigator.clipboard stub
    // (attachClipboardStubToView), so a plain
    // `Object.assign(navigator, { clipboard: ... })` is silently discarded
    // (or, once set up elsewhere, throws on the getter-only property).
    // Spy on the stub's own writeText method instead of replacing the object.
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    render(<RecoveryCodesDisplay codes={codes} onConfirmed={() => {}} />);

    // Act
    await user.click(screen.getByRole("button", { name: /copy/i }));

    // Assert
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("AAAA-1111"));
  });

  it("test_recovery_codes_display_continue_control_is_disabled_until_save_confirmation_is_checked", async () => {
    // Arrange
    const onConfirmed = vi.fn();
    const user = userEvent.setup();
    render(<RecoveryCodesDisplay codes={codes} onConfirmed={onConfirmed} />);
    const continueButton = screen.getByRole("button", { name: /continue/i });

    // Assert (before)
    expect(continueButton).toBeDisabled();

    // Act
    await user.click(screen.getByRole("checkbox", { name: /saved/i }));

    // Assert (after)
    expect(continueButton).toBeEnabled();
    await user.click(continueButton);
    expect(onConfirmed).toHaveBeenCalledTimes(1);
  });

  it("test_recovery_codes_display_never_writes_codes_to_local_storage_session_storage_or_console", async () => {
    // Arrange
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    // See the copy-control test above: spy on user-event's own clipboard
    // stub rather than assigning a new navigator.clipboard object.
    const user = userEvent.setup();
    vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue(undefined);
    render(<RecoveryCodesDisplay codes={codes} onConfirmed={() => {}} />);

    // Act
    await user.click(screen.getByRole("button", { name: /copy/i }));
    await user.click(screen.getByRole("checkbox", { name: /saved/i }));

    // Assert
    expect(setItemSpy).not.toHaveBeenCalled();
    for (const spy of [consoleLogSpy, consoleWarnSpy, consoleErrorSpy]) {
      for (const call of spy.mock.calls) {
        expect(call.join(" ")).not.toMatch(/AAAA-1111|BBBB-2222|CCCC-3333/);
      }
    }
  });
});
