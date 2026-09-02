"use client";

import { useEffect, useState } from "react";
import { Loader2, Shield, ShieldOff, Trash2, Key } from "lucide-react";
import { getAllUsers, toggleUserActive, setUserRole, adminResetPassword, deleteUser } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { AdminUser } from "@/lib/types";

export default function AdminUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    getAllUsers().then(setUsers).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleToggleActive = async (u: AdminUser) => {
    await toggleUserActive(u.id, !u.is_active);
    load();
  };

  const handleToggleRole = async (u: AdminUser) => {
    setError(null);
    try {
      await setUserRole(u.id, u.role === "admin" ? "user" : "admin");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update role");
    }
  };

  const handleResetPassword = async (u: AdminUser) => {
    const newPassword = window.prompt(`New password for ${u.email} (min 8 characters)`);
    if (!newPassword || newPassword.length < 8) return;
    await adminResetPassword(u.id, newPassword);
    window.alert("Password reset.");
  };

  const handleDelete = async (u: AdminUser) => {
    setError(null);
    if (!window.confirm(`Delete ${u.email}? This can't be undone.`)) return;
    try {
      await deleteUser(u.id);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete user");
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-text-muted">
        <Loader2 size={18} className="animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 font-mono text-lg text-text-primary">Users</h1>
      {error && (
        <div className="mb-4 rounded border border-red-900/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">{error}</div>
      )}
      <div className="overflow-hidden rounded-lg border border-hairline bg-surface">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-hairline text-left text-xs text-text-muted">
              <th className="px-4 py-2 font-normal">Email</th>
              <th className="px-4 py-2 font-normal">Role</th>
              <th className="px-4 py-2 font-normal">Status</th>
              <th className="px-4 py-2 font-normal">Joined</th>
              <th className="px-4 py-2 font-normal">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-hairline text-text-primary">
                <td className="px-4 py-2">{u.email}</td>
                <td className="px-4 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-mono ${u.role === "admin" ? "bg-accent/10 text-accent" : "bg-elevated text-text-muted"}`}>
                    {u.role}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-mono ${u.is_active ? "bg-verified/10 text-verified" : "bg-red-950/30 text-red-400"}`}>
                    {u.is_active ? "active" : "disabled"}
                  </span>
                </td>
                <td className="px-4 py-2 text-text-muted">{new Date(u.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggleActive(u)}
                      disabled={u.id === currentUser?.id}
                      title={u.is_active ? "Disable account" : "Enable account"}
                      className="text-text-muted hover:text-accent disabled:opacity-30"
                    >
                      {u.is_active ? <ShieldOff size={14} /> : <Shield size={14} />}
                    </button>
                    <button
                      onClick={() => handleToggleRole(u)}
                      disabled={u.id === currentUser?.id}
                      title={u.role === "admin" ? "Demote to user" : "Promote to admin"}
                      className="text-text-muted hover:text-accent disabled:opacity-30"
                    >
                      <Shield size={14} className={u.role === "admin" ? "fill-accent/20" : ""} />
                    </button>
                    <button onClick={() => handleResetPassword(u)} title="Reset password" className="text-text-muted hover:text-accent">
                      <Key size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(u)}
                      disabled={u.id === currentUser?.id}
                      title="Delete user"
                      className="text-text-muted hover:text-red-400 disabled:opacity-30"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}