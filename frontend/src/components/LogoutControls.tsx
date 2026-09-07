// FE-AC5: the "Log out" / "Log out everywhere" controls. Deliberately placed
// in `components/`, not written inline in `layouts/AppShell.tsx` — closing
// docs/reviews/plans/US-5.1-plan-review.md's [Low] finding that AppShell
// calling useLogout/useLogoutAll would need a `hooks/` import the
// AGENTS.md §3 `routes/ (guards + layout)` row does not list. `components/`
// IS authorized to import `hooks/`, so AppShell simply renders this child
// component rather than owning the import itself.
import { useNavigate } from "react-router-dom";
import { useLogout } from "../hooks/useLogout";
import { useLogoutAll } from "../hooks/useLogoutAll";

export function LogoutControls() {
  const navigate = useNavigate();
  const logout = useLogout();
  const logoutAll = useLogoutAll();

  async function handleLogout() {
    await logout.mutateAsync();
    navigate("/login");
  }

  async function handleLogoutAll() {
    await logoutAll.mutateAsync();
    navigate("/login");
  }

  return (
    <div>
      <button type="button" onClick={handleLogout}>
        Log out
      </button>
      <button type="button" onClick={handleLogoutAll}>
        Log out everywhere
      </button>
    </div>
  );
}
