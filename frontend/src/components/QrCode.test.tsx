// Integration test for QrCode (Task T5, Plan Change 9/Risk 2). Wraps the
// `qrcode.react` dependency (human-approved at HUMAN_PLAN_APPROVAL — see
// docs/plans/US-5.2-implementation-plan.md Risk 2) so the third-party import
// stays isolated to this one adapter file. Assumption #5/FR-5: the
// `otpauth_uri` QR is rendered locally, never via an external service — the
// value must never leave the browser as a network request. This file fails
// at module resolution until `frontend/package.json` (Task T5) adds
// `qrcode.react` — expected RED, see the generation report.
import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { server } from "../test/mswServer";
import { QrCode } from "./QrCode";

const otpauthUri =
  "otpauth://totp/CustomerPortal:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=CustomerPortal";

describe("QrCode", () => {
  it("test_qr_code_renders_an_svg_representation_of_the_provided_value", () => {
    // Arrange / Act
    const { container } = render(<QrCode value={otpauthUri} />);

    // Assert
    expect(container.querySelector("svg")).not.toBeNull();
  });

  it("test_qr_code_fires_no_network_request_while_rendering", () => {
    // Arrange
    let unexpectedRequestSeen = false;
    server.events.on("request:start", () => {
      unexpectedRequestSeen = true;
    });

    // Act
    render(<QrCode value={otpauthUri} />);

    // Assert
    expect(unexpectedRequestSeen).toBe(false);
  });

  it("test_qr_code_never_logs_the_provided_value_to_the_console", () => {
    // Arrange
    const consoleLogSpy = vi.spyOn(console, "log").mockImplementation(() => {});
    const consoleWarnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    // Act
    render(<QrCode value={otpauthUri} />);

    // Assert
    for (const spy of [consoleLogSpy, consoleWarnSpy, consoleErrorSpy]) {
      for (const call of spy.mock.calls) {
        expect(call.join(" ")).not.toContain("JBSWY3DPEHPK3PXP");
      }
      spy.mockRestore();
    }
  });
});
