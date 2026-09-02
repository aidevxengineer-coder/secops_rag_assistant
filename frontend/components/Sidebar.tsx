"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useParams } from "next/navigation";
import { Plus, Folder, FolderPlus, MessageSquare, ChevronDown, ChevronRight, Trash2, Pencil, LogOut, ShieldHalf } from "lucide-react";
import { listProjects, createProject, listChats, createChat, deleteChat, renameChat, deleteProject } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import type { Project, ChatSummary } from "@/lib/types";
import { ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";


export default function Sidebar() {
  const router = useRouter();
  const params = useParams<{ chatId?: string }>();
  const { user, logout } = useAuth();
  // inside the component, alongside the existing params:
  const pathname = usePathname();

  const [projects, setProjects] = useState<Project[]>([]);
  const [chatsByProject, setChatsByProject] = useState<Record<string, ChatSummary[]>>({});
  const [unfiledChats, setUnfiledChats] = useState<ChatSummary[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [editingChatId, setEditingChatId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [projectList, allChats] = await Promise.all([listProjects(), listChats()]);
      setProjects(projectList);

      const grouped: Record<string, ChatSummary[]> = {};
      const unfiled: ChatSummary[] = [];
      for (const chat of allChats as ChatSummary[]) {
        if (chat.project_id) {
          grouped[chat.project_id] = grouped[chat.project_id] || [];
          grouped[chat.project_id].push(chat);
        } else {
          unfiled.push(chat);
        }
      }
      setChatsByProject(grouped);
      setUnfiledChats(unfiled);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [pathname]); // re-fetch chat list every time the route changes

  const handleNewChat = async (projectId: string | null = null) => {
    const chat = await createChat(projectId);
    await loadAll();
    router.push(`/chat/${chat.id}`);
  };

  const handleNewProject = async () => {
    const name = window.prompt("Project name");
    if (!name?.trim()) return;
    await createProject(name.trim());
    await loadAll();
  };

  const handleDeleteChat = async (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation();
    if (!window.confirm("Delete this chat? This can't be undone.")) return;
    await deleteChat(chatId);
    await loadAll();
    if (params?.chatId === chatId) router.push("/chat");
  };

  const handleDeleteProject = async (e: React.MouseEvent, projectId: string) => {
    e.stopPropagation();
    if (!window.confirm("Delete this project? Chats inside will be kept but unfiled.")) return;
    await deleteProject(projectId);
    await loadAll();
  };

  const startRename = (e: React.MouseEvent, chat: ChatSummary) => {
    e.stopPropagation();
    setEditingChatId(chat.id);
    setEditTitle(chat.title);
  };

  const commitRename = async (chatId: string) => {
    if (editTitle.trim()) {
      await renameChat(chatId, editTitle.trim());
      await loadAll();
    }
    setEditingChatId(null);
  };

  const toggleProject = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const renderChatRow = (chat: ChatSummary) => {
    const isActive = params?.chatId === chat.id;
    return (
      <div
        key={chat.id}
        onClick={() => router.push(`/chat/${chat.id}`)}
        className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm cursor-pointer ${
          isActive ? "bg-accent/10 text-accent" : "text-text-muted hover:bg-elevated hover:text-text-primary"
        }`}
      >
        <MessageSquare size={13} className="shrink-0" />
        {editingChatId === chat.id ? (
          <input
            autoFocus
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={() => commitRename(chat.id)}
            onKeyDown={(e) => e.key === "Enter" && commitRename(chat.id)}
            onClick={(e) => e.stopPropagation()}
            className="flex-1 rounded border border-hairline bg-surface px-1 py-0.5 text-sm text-text-primary outline-none"
          />
        ) : (
          <span className="flex-1 truncate">{chat.title}</span>
        )}
        <button onClick={(e) => startRename(e, chat)} className="hidden shrink-0 hover:text-accent group-hover:block">
          <Pencil size={12} />
        </button>
        <button onClick={(e) => handleDeleteChat(e, chat.id)} className="hidden shrink-0 hover:text-red-400 group-hover:block">
          <Trash2 size={12} />
        </button>
      </div>
    );
  };

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-hairline bg-surface">
      <div className="flex items-center gap-2 border-b border-hairline px-4 py-3.5">
        <ShieldHalf size={18} className="text-accent" strokeWidth={2} />
        <span className="font-mono text-sm font-semibold text-text-primary">SecOps Copilot</span>
      </div>

      <div className="flex flex-col gap-1.5 p-3">
        <button
          onClick={() => handleNewChat(null)}
          className="flex items-center gap-2 rounded-md border border-hairline bg-elevated px-3 py-2 text-sm text-text-primary hover:border-accent"
        >
          <Plus size={14} />
          New chat
        </button>
        <button
          onClick={handleNewProject}
          className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-text-muted hover:bg-elevated hover:text-text-primary"
        >
          <FolderPlus size={14} />
          New project
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {loading ? (
          <p className="px-2 py-2 text-xs text-text-muted">Loading...</p>
        ) : (
          <>
            {projects.map((project) => {
              const isOpen = expanded.has(project.id);
              const chats = chatsByProject[project.id] || [];
              return (
                <div key={project.id} className="mb-1">
                  <div
                    onClick={() => toggleProject(project.id)}
                    className="group flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-text-primary cursor-pointer hover:bg-elevated"
                  >
                    {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                    <Folder size={13} className="shrink-0 text-accent" />
                    <span className="flex-1 truncate">{project.name}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleNewChat(project.id);
                      }}
                      className="hidden shrink-0 hover:text-accent group-hover:block"
                      title="New chat in this project"
                    >
                      <Plus size={12} />
                    </button>
                    <button
                      onClick={(e) => handleDeleteProject(e, project.id)}
                      className="hidden shrink-0 hover:text-red-400 group-hover:block"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                  {isOpen && (
                    <div className="ml-4 flex flex-col gap-0.5 border-l border-hairline pl-2">
                      {chats.length === 0 ? (
                        <p className="px-2 py-1 text-xs text-text-muted">No chats yet</p>
                      ) : (
                        chats.map(renderChatRow)
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            {unfiledChats.length > 0 && (
              <div className="mt-3">
                <p className="px-2 pb-1 font-mono text-[10px] uppercase tracking-wide text-text-muted">Chats</p>
                <div className="flex flex-col gap-0.5">{unfiledChats.map(renderChatRow)}</div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="border-t border-hairline p-3">
  {user?.role === "admin" && (
    <button
      onClick={() => router.push("/admin")}
      className="mb-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs text-text-muted hover:bg-elevated hover:text-accent"
    >
      <ShieldCheck size={13} />
      Admin dashboard
    </button>
  )}
  <div className="flex items-center justify-between px-1">
    <span className="truncate text-xs text-text-muted">{user?.email}</span>
    <button onClick={logout} className="shrink-0 text-text-muted hover:text-red-400" title="Log out">
      <LogOut size={14} />
    </button>
  </div>
</div>
    </aside>
  );
}