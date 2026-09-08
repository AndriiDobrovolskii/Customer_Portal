// US-5.2 Plan Change 9: thin adapter isolating the qrcode.react dependency
// (human-approved at HUMAN_PLAN_APPROVAL, Plan Risk 2) to this one file — if
// a different library is approved later, only this file's internals change.
// Renders the otpauth_uri QR locally, in the browser, never via an external
// service (Assumption #5/FR-5) — no network call, no logging of `value`.
import { QRCodeSVG } from "qrcode.react";

export interface QrCodeProps {
  value: string;
}

export function QrCode({ value }: QrCodeProps) {
  return <QRCodeSVG value={value} role="img" aria-label="Multi-factor authentication setup QR" />;
}
