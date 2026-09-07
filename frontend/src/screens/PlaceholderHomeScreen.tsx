// FR-2/FR-3's post-login landing target. OD-8 (docs/decisions/US-5.1-open-decisions.md,
// still OPEN): content is intentionally minimal/placeholder pending
// resolution — Support Tickets UI (Story 5.2) does not exist yet.
import { useAuthStore } from "../store/authStore";
import { MfaEnrollmentBanner } from "../components/MfaEnrollmentBanner";

export function PlaceholderHomeScreen() {
  const { user, mfaEnrollmentDeadline } = useAuthStore();

  return (
    <section>
      <MfaEnrollmentBanner deadline={mfaEnrollmentDeadline} />
      <h1>Welcome{user ? `, ${user.email}` : ""}</h1>
      <p>You are logged in to the Customer Portal.</p>
    </section>
  );
}
