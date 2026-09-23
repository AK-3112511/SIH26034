"use client";
/**
 * §3 Screen 9 — Admin: User Management (Phase 6.4)
 * Assign field_lmo/senior_lmo/admin roles, assign district/zone. Admin-only
 * per §12 of the blueprint. Route guard mirrors the pattern already used by
 * /admin/rulesets since Phase 4.
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, CheckCircle2, Plus, XCircle } from "lucide-react";
import { AppShell } from "@/app/components/AppShell";
import { ErrorBanner } from "@/app/components/ui/ErrorBanner";
import { CalibrationRuler } from "@/app/components/CalibrationRuler";
import { AdminGuard } from "@/app/components/ui/AdminGuard";
import { adminUsersApi, type UserResponse } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Role = "field_lmo" | "senior_lmo" | "admin";
const ROLE_OPTIONS: Role[] = ["field_lmo", "senior_lmo", "admin"];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
}

function UserRow({
  user,
  onSaved,
}: {
  user: UserResponse;
  onSaved: (updated: UserResponse) => void;
}) {
  const [role, setRole] = useState<Role>(user.role as Role);
  const [district, setDistrict] = useState(user.district ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = role !== user.role || district !== (user.district ?? "");

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await adminUsersApi.update(user.id, {
        role,
        district: district.trim() || null,
      });
      onSaved(data);
    } catch (err) {
      setError(apiErrorMessage(err, "The change could not be saved."));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async () => {
    setSaving(true);
    setError(null);
    try {
      const { data } = await adminUsersApi.update(user.id, { is_active: !user.is_active });
      onSaved(data);
    } catch (err) {
      setError(apiErrorMessage(err, "The account status could not be changed."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <tr className="hover:bg-ink-900/[0.03] transition-colors">
      <td className="pl-4 py-3 align-middle">
        <span className="font-body text-sm font-semibold text-ink-900">{user.full_name}</span>
        <div className="font-mono text-xs text-ink-600">{user.username}</div>
      </td>
      <td className="py-3 align-middle font-mono text-xs text-ink-600">{user.email}</td>
      <td className="py-3 align-middle">
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
          className="form-input text-xs py-1.5 min-h-[36px] w-36"
          aria-label={`Role for ${user.username}`}
        >
          {ROLE_OPTIONS.map((r) => (
            <option key={r} value={r}>
              {r.replace("_", " ")}
            </option>
          ))}
        </select>
      </td>
      <td className="py-3 align-middle">
        <input
          type="text"
          value={district}
          onChange={(e) => setDistrict(e.target.value)}
          placeholder="District / zone"
          className="form-input text-xs py-1.5 min-h-[36px] w-32"
          aria-label={`District for ${user.username}`}
        />
      </td>
      <td className="py-3 align-middle text-center">
        <button
          type="button"
          onClick={handleToggleActive}
          disabled={saving}
          className="status-chip"
          style={
            user.is_active
              ? { color: "#1E7A4D", backgroundColor: "rgba(30,122,77,0.1)", borderColor: "rgba(30,122,77,0.2)" }
              : { color: "#6B7280", backgroundColor: "rgba(107,114,128,0.1)", borderColor: "rgba(107,114,128,0.2)" }
          }
        >
          {user.is_active ? <CheckCircle2 size={11} /> : <XCircle size={11} />}
          {user.is_active ? "Active" : "Inactive"}
        </button>
      </td>
      <td className="py-3 align-middle font-mono text-xs text-ink-600">{formatDate(user.created_at)}</td>
      <td className="pr-4 py-3 align-middle text-right">
        {error && <span className="font-body text-xs text-verdict-fail mr-2">{error}</span>}
        <button
          type="button"
          onClick={handleSave}
          disabled={!dirty || saving}
          className="btn-secondary text-xs px-3 py-1 min-h-[36px]"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </td>
    </tr>
  );
}

function UserManagementScreen() {
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [formUsername, setFormUsername] = useState("");
  const [formEmail, setFormEmail] = useState("");
  const [formFullName, setFormFullName] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formRole, setFormRole] = useState<Role>("field_lmo");
  const [formDistrict, setFormDistrict] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await adminUsersApi.list();
      setUsers(data.users);
    } catch (err) {
      setError(apiErrorMessage(err, "The officer list could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleUserSaved = (updated: UserResponse) => {
    setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
  };

  const resetForm = () => {
    setFormUsername("");
    setFormEmail("");
    setFormFullName("");
    setFormPassword("");
    setFormRole("field_lmo");
    setFormDistrict("");
    setFormError(null);
  };

  const handleCreate = async () => {
    setFormError(null);
    if (!formUsername.trim() || !formEmail.trim() || !formFullName.trim() || formPassword.length < 8) {
      setFormError("Username, email, full name, and an 8+ character password are all required.");
      return;
    }
    setSaving(true);
    try {
      await adminUsersApi.create({
        username: formUsername.trim(),
        email: formEmail.trim(),
        password: formPassword,
        full_name: formFullName.trim(),
        role: formRole,
        district: formDistrict.trim() || null,
      });
      resetForm();
      setShowForm(false);
      await fetchUsers();
    } catch (err) {
      setFormError(apiErrorMessage(err, "The officer account could not be created."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h1 className="font-display text-2xl font-bold text-ink-900">
            Officer accounts
          </h1>
          <p className="font-body text-sm text-ink-600 mt-1">
            Assign roles and jurisdictions. Field officers use the handset; senior officers
            and administrators use this dashboard.
          </p>
        </div>
      </div>

      <CalibrationRuler className="mb-6" />

      <ErrorBanner className="mb-6" message={error} />

      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-lg font-semibold text-ink-900">Officers</h2>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="btn-secondary text-xs px-3 py-1.5 min-h-[40px] inline-flex items-center gap-1.5"
        >
          <Plus size={14} />
          {showForm ? "Cancel" : "Add an officer"}
        </button>
      </div>

      {showForm && (
        <div className="card-surface mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label htmlFor="u-username" className="form-label">
                Username
              </label>
              <input
                id="u-username"
                type="text"
                value={formUsername}
                onChange={(e) => setFormUsername(e.target.value)}
                className="form-input text-sm"
              />
            </div>
            <div>
              <label htmlFor="u-email" className="form-label">
                Email
              </label>
              <input
                id="u-email"
                type="email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                className="form-input text-sm"
              />
            </div>
            <div>
              <label htmlFor="u-fullname" className="form-label">
                Full Name
              </label>
              <input
                id="u-fullname"
                type="text"
                value={formFullName}
                onChange={(e) => setFormFullName(e.target.value)}
                className="form-input text-sm"
              />
            </div>
            <div>
              <label htmlFor="u-password" className="form-label">
                Temporary Password
              </label>
              <input
                id="u-password"
                type="password"
                value={formPassword}
                onChange={(e) => setFormPassword(e.target.value)}
                className="form-input text-sm"
                minLength={8}
              />
            </div>
            <div>
              <label htmlFor="u-role" className="form-label">
                Role
              </label>
              <select
                id="u-role"
                value={formRole}
                onChange={(e) => setFormRole(e.target.value as Role)}
                className="form-input text-sm"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r} value={r}>
                    {r.replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="u-district" className="form-label">
                District / Zone
              </label>
              <input
                id="u-district"
                type="text"
                value={formDistrict}
                onChange={(e) => setFormDistrict(e.target.value)}
                placeholder="e.g. Chennai"
                className="form-input text-sm"
              />
            </div>
          </div>

          {formError && (
            <div
              role="alert"
              className="mb-4 p-3 rounded-[4px] text-xs font-body"
              style={{
                backgroundColor: "rgba(179,38,30,0.08)",
                border: "1px solid rgba(179,38,30,0.3)",
                color: "#B3261E",
              }}
            >
              {formError}
            </div>
          )}

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                resetForm();
                setShowForm(false);
              }}
              className="btn-secondary text-xs px-4 py-1.5 min-h-[40px]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreate}
              disabled={saving}
              className="btn-primary text-xs px-4 py-1.5 min-h-[40px]"
            >
              {saving ? "Creating…" : "Create User"}
            </button>
          </div>
        </div>
      )}

      <div className="card-surface p-0 overflow-x-auto shadow-sm">
        <table className="data-table w-full" aria-label="Officer accounts">
          <thead>
            <tr>
              <th className="pl-4 py-3 font-semibold">Officer</th>
              <th className="py-3 font-semibold">Email</th>
              <th className="py-3 font-semibold">Role</th>
              <th className="py-3 font-semibold">District / Zone</th>
              <th className="py-3 font-semibold text-center">Status</th>
              <th className="py-3 font-semibold">Created</th>
              <th className="py-3 pr-4 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="py-16 text-center">
                  <span className="font-mono text-sm text-ink-600 animate-pulse">
                    Loading officer accounts…
                  </span>
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-16 text-center">
                  <p className="font-display text-base font-semibold text-ink-900">
                    No officer accounts yet
                  </p>
                </td>
              </tr>
            ) : (
              users.map((user) => <UserRow key={user.id} user={user} onSaved={handleUserSaved} />)
            )}
          </tbody>
        </table>
      </div>
    </AppShell>
  );
}

export default function AdminUsersPage() {
  return (
    <AdminGuard>
      <UserManagementScreen />
    </AdminGuard>
  );
}
