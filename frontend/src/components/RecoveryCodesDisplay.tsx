// FR-5's one-time recovery-code display: copy (navigator.clipboard) and
// download (local Blob/object-URL, no network) support, plus the explicit
// "I have saved these" confirmation gate the flow cannot complete without.
// Never writes to any storage API — codes are held only in the parent's
// transient component state and passed here as a prop (NFR, PS-AC5).
import { useState } from "react";

export interface RecoveryCodesDisplayProps {
  codes: string[];
  onConfirmed: () => void;
}

export function RecoveryCodesDisplay({ codes, onConfirmed }: RecoveryCodesDisplayProps) {
  const [saved, setSaved] = useState(false);

  function handleCopy() {
    void navigator.clipboard.writeText(codes.join("\n"));
  }

  function handleDownload() {
    const blob = new Blob([codes.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "recovery-codes.txt";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section>
      <h2>Save your recovery codes</h2>
      <p>
        Store these recovery codes somewhere safe. Each code can be used once to sign in if you lose access to
        your authenticator app. They will not be shown again.
      </p>
      <ul>
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <button type="button" onClick={handleCopy}>
        Copy codes
      </button>
      <button type="button" onClick={handleDownload}>
        Download codes
      </button>
      <div>
        <input
          id="recovery-codes-saved"
          type="checkbox"
          checked={saved}
          onChange={(event) => setSaved(event.target.checked)}
        />
        <label htmlFor="recovery-codes-saved">I have saved these codes</label>
      </div>
      <button type="button" disabled={!saved} onClick={onConfirmed}>
        Continue
      </button>
    </section>
  );
}
