import { apiFetch } from "./api-client";
import type { ChatResponse } from "./types";

export async function sendMessage(message: string, chatId: string, traceId: string): Promise<ChatResponse> {
  const res = await apiFetch(`/chat`, {
    method: "POST",
    body: JSON.stringify({ message, chat_id: chatId, trace_id: traceId }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Backend error (${res.status}): ${detail || res.statusText}`);
  }
  return res.json();
}

export async function getChatMessages(chatId: string) {
  const res = await apiFetch(`/chats/${chatId}/messages`);
  if (!res.ok) throw new Error("Failed to load chat history");
  return res.json();
}

// --- projects ---
export async function listProjects() {
  const res = await apiFetch(`/projects`);
  if (!res.ok) throw new Error("Failed to load projects");
  return res.json();
}

export async function createProject(name: string) {
  const res = await apiFetch(`/projects`, { method: "POST", body: JSON.stringify({ name }) });
  if (!res.ok) throw new Error("Failed to create project");
  return res.json();
}

export async function deleteProject(projectId: string) {
  const res = await apiFetch(`/projects/${projectId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete project");
}

// --- chats ---
export async function listChats(projectId?: string | null) {
  const q = projectId ? `?project_id=${projectId}` : "";
  const res = await apiFetch(`/chats${q}`);
  if (!res.ok) throw new Error("Failed to load chats");
  return res.json();
}

export async function createChat(projectId?: string | null, title = "New Chat") {
  const res = await apiFetch(`/chats`, {
    method: "POST",
    body: JSON.stringify({ project_id: projectId ?? null, title }),
  });
  if (!res.ok) throw new Error("Failed to create chat");
  return res.json();
}

export async function renameChat(chatId: string, title: string) {
  const res = await apiFetch(`/chats/${chatId}`, { method: "PATCH", body: JSON.stringify({ title }) });
  if (!res.ok) throw new Error("Failed to rename chat");
}

export async function deleteChat(chatId: string) {
  const res = await apiFetch(`/chats/${chatId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete chat");
}

// --- admin: analytics ---
export async function getLatencyStats(hours = 24) {
  const res = await apiFetch(`/admin/stats/latency?hours=${hours}`);
  if (!res.ok) throw new Error("Failed to load latency stats");
  return res.json();
}

export async function getFailureStats(hours = 24) {
  const res = await apiFetch(`/admin/stats/failures?hours=${hours}`);
  if (!res.ok) throw new Error("Failed to load failure stats");
  return res.json();
}

export async function getCostStats(hours = 24) {
  const res = await apiFetch(`/admin/stats/costs?hours=${hours}`);
  if (!res.ok) throw new Error("Failed to load cost stats");
  return res.json();
}

export async function getUserUsageStats(hours = 24) {
  const res = await apiFetch(`/admin/stats/users?hours=${hours}`);
  if (!res.ok) throw new Error("Failed to load user usage stats");
  return res.json();
}

export async function getDailyActivity(days = 14) {
  const res = await apiFetch(`/admin/stats/activity?days=${days}`);
  if (!res.ok) throw new Error("Failed to load activity stats");
  return res.json();
}

// --- admin: user management ---
export async function getAllUsers() {
  const res = await apiFetch(`/admin/users`);
  if (!res.ok) throw new Error("Failed to load users");
  return res.json();
}

export async function toggleUserActive(userId: string, isActive: boolean) {
  const res = await apiFetch(`/admin/users/${userId}/active`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: isActive }),
  });
  if (!res.ok) throw new Error("Failed to update user");
}

export async function setUserRole(userId: string, role: "user" | "admin") {
  const res = await apiFetch(`/admin/users/${userId}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update role");
  }
}

export async function adminResetPassword(userId: string, newPassword: string) {
  const res = await apiFetch(`/admin/users/${userId}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
  if (!res.ok) throw new Error("Failed to reset password");
}

export async function deleteUser(userId: string) {
  const res = await apiFetch(`/admin/users/${userId}`, { method: "DELETE" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete user");
  }
}

export async function getWallLatencyStats(hours = 24) {
  const res = await apiFetch(`/admin/stats/wall-latency?hours=${hours}`);
  if (!res.ok) throw new Error("Failed to load wall latency stats");
  return res.json();
}