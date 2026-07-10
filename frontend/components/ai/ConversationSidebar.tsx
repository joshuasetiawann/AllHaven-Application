"use client";

import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FolderInput,
  FolderPlus,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { cn } from "@/lib/format";
import type { ChatGroup, ChatSession } from "@/types";

export interface ConversationSidebarProps {
  groups: ChatGroup[];
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: (groupId?: string | null) => void;
  onCreateGroup: () => void;
  onRenameChat: (s: ChatSession) => void;
  onDeleteChat: (s: ChatSession) => void;
  onMoveChat: (s: ChatSession, groupId: string | null) => void;
  onRenameGroup: (g: ChatGroup) => void;
  onDeleteGroup: (g: ChatGroup) => void;
  onCloseMobile?: () => void;
}

function ChatRow({
  s,
  active,
  groups,
  onSelect,
  onRenameChat,
  onDeleteChat,
  onMoveChat,
}: {
  s: ChatSession;
  active: boolean;
  groups: ChatGroup[];
  onSelect: (id: string) => void;
  onRenameChat: (s: ChatSession) => void;
  onDeleteChat: (s: ChatSession) => void;
  onMoveChat: (s: ChatSession, groupId: string | null) => void;
}) {
  const [menu, setMenu] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  return (
    <div className="group/row relative">
      <button
        onClick={() => onSelect(s.id)}
        className={cn(
          "flex w-full items-center gap-2 rounded-md border px-2.5 py-2 text-left text-[13px] transition-colors",
          active
            ? "border-primary/30 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.14),rgb(var(--color-secondary)/0.08))] text-content shadow-[0_0_20px_rgb(var(--color-primary)/0.12)]"
            : "border-transparent text-content-muted hover:bg-surface-raised/60 hover:text-content",
        )}
      >
        <span className={cn("min-w-0 flex-1 truncate", active && "font-semibold")}>{s.title || "New Chat"}</span>
        <span
          role="button"
          tabIndex={0}
          onClick={(e) => {
            e.stopPropagation();
            setMenu((o) => !o);
            setMoveOpen(false);
          }}
          className="shrink-0 rounded p-0.5 text-content-subtle opacity-0 hover:bg-surface-raised hover:text-content group-hover/row:opacity-100 aria-expanded:opacity-100"
          aria-expanded={menu}
          aria-label="Conversation options"
        >
          <MoreHorizontal size={15} />
        </span>
      </button>

      {menu ? (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setMenu(false)} />
          <div className="absolute right-1 top-9 z-40 w-44 animate-scale-in rounded-md border border-border bg-bg-deep/95 p-1 shadow-panel backdrop-blur-md">
            <button
              onClick={() => { setMenu(false); onRenameChat(s); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] text-content hover:bg-surface-raised/70"
            >
              <Pencil size={13} /> Rename
            </button>
            <button
              onClick={() => setMoveOpen((o) => !o)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] text-content hover:bg-surface-raised/70"
            >
              <FolderInput size={13} /> Move to… <ChevronRight size={12} className="ml-auto" />
            </button>
            {moveOpen ? (
              <div className="mt-1 max-h-44 overflow-y-auto border-t border-border pt-1">
                {s.group_id ? (
                  <button
                    onClick={() => { setMenu(false); onMoveChat(s, null); }}
                    className="block w-full rounded-md px-2 py-1.5 text-left text-[12.5px] text-content-muted hover:bg-surface-raised/70"
                  >
                    No group
                  </button>
                ) : null}
                {groups.filter((g) => g.id !== s.group_id).map((g) => (
                  <button
                    key={g.id}
                    onClick={() => { setMenu(false); onMoveChat(s, g.id); }}
                    className="block w-full truncate rounded-md px-2 py-1.5 text-left text-[12.5px] text-content hover:bg-surface-raised/70"
                  >
                    {g.name}
                  </button>
                ))}
                {groups.length === 0 ? (
                  <p className="px-2 py-1.5 text-[12px] text-content-subtle">No groups yet.</p>
                ) : null}
              </div>
            ) : null}
            <button
              onClick={() => { setMenu(false); onDeleteChat(s); }}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] text-danger hover:bg-danger/10"
            >
              <Trash2 size={13} /> Delete
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

export function ConversationSidebar(props: ConversationSidebarProps) {
  const { groups, sessions, activeId } = props;
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? sessions.filter((s) => (s.title || "new chat").toLowerCase().includes(q)) : sessions;
  }, [sessions, query]);

  const ungrouped = filtered.filter((s) => !s.group_id);
  const byGroup = (gid: string) => filtered.filter((s) => s.group_id === gid);

  const rowProps = {
    groups,
    onSelect: props.onSelect,
    onRenameChat: props.onRenameChat,
    onDeleteChat: props.onDeleteChat,
    onMoveChat: props.onMoveChat,
  };

  return (
    <aside className="flex h-full w-full flex-col">
      <div className="flex items-center justify-between gap-2 px-4 pb-1 pt-4">
        <h2 className="text-sm font-semibold text-content">Conversations</h2>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => props.onNewChat(null)}
            aria-label="New chat"
            title="New chat"
            className="grad-primary flex h-[30px] w-[30px] items-center justify-center rounded-sm text-primary-fg shadow-[0_0_16px_rgb(var(--color-primary)/0.4)] transition-all hover:brightness-[1.06] focus-ring"
          >
            <MessageSquarePlus size={15} />
          </button>
          {props.onCloseMobile ? (
            <button onClick={props.onCloseMobile} className="rounded p-1 text-content-subtle hover:text-content lg:hidden" aria-label="Close">
              <X size={16} />
            </button>
          ) : null}
        </div>
      </div>

      <div className="px-4 py-2.5">
        <div className="flex items-center gap-2 rounded border border-border bg-white/[0.03] px-3">
          <Search size={14} className="shrink-0 text-content-subtle" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats…"
            className="h-9 min-w-0 flex-1 bg-transparent text-[12.5px] text-content placeholder:text-content-subtle focus:outline-none"
          />
        </div>
      </div>

      <div className="custom-scrollbar min-h-0 flex-1 space-y-3 overflow-y-auto px-2 pb-3">
        {/* Groups / Projects */}
        <div>
          <div className="flex items-center justify-between px-1.5 py-1">
            <p className="label-mono">Groups</p>
            <button onClick={props.onCreateGroup} className="rounded p-0.5 text-content-subtle hover:text-content" aria-label="New group">
              <FolderPlus size={14} />
            </button>
          </div>
          {groups.length === 0 ? (
            <p className="px-2 py-1 text-[12px] text-content-subtle">No groups. Create one to organize chats.</p>
          ) : (
            <div className="space-y-0.5">
              {groups.map((g) => {
                const open = !collapsed[g.id];
                const chats = byGroup(g.id);
                return (
                  <div key={g.id}>
                    <div className="group/grp flex items-center gap-1 rounded-lg px-1.5 py-1.5 hover:bg-surface-raised/40">
                      <button
                        onClick={() => setCollapsed((c) => ({ ...c, [g.id]: !c[g.id] }))}
                        className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-[13px] text-content"
                      >
                        {open ? <ChevronDown size={13} className="shrink-0 text-content-subtle" /> : <ChevronRight size={13} className="shrink-0 text-content-subtle" />}
                        <span className="truncate font-medium">{g.name}</span>
                        <span className="text-[11px] text-content-subtle">{chats.length}</span>
                      </button>
                      <button onClick={() => props.onNewChat(g.id)} className="rounded p-0.5 text-content-subtle opacity-0 hover:text-content group-hover/grp:opacity-100" aria-label="New chat in group">
                        <Plus size={13} />
                      </button>
                      <button onClick={() => props.onRenameGroup(g)} className="rounded p-0.5 text-content-subtle opacity-0 hover:text-content group-hover/grp:opacity-100" aria-label="Rename group">
                        <Pencil size={12} />
                      </button>
                      <button onClick={() => props.onDeleteGroup(g)} className="rounded p-0.5 text-content-subtle opacity-0 hover:text-danger group-hover/grp:opacity-100" aria-label="Delete group">
                        <Trash2 size={12} />
                      </button>
                    </div>
                    {open ? (
                      <div className="ml-3 border-l border-border pl-1.5">
                        {chats.length === 0 ? (
                          <p className="px-2 py-1 text-[12px] text-content-subtle">Empty</p>
                        ) : (
                          chats.map((s) => <ChatRow key={s.id} s={s} active={s.id === activeId} {...rowProps} />)
                        )}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent (ungrouped) */}
        <div>
          <p className="label-mono px-1.5 py-1">Recent Chats</p>
          {ungrouped.length === 0 ? (
            <p className="px-2 py-1 text-[12px] text-content-subtle">{query ? "No matches." : "No chats yet — start one."}</p>
          ) : (
            <div className="space-y-0.5">
              {ungrouped.map((s) => <ChatRow key={s.id} s={s} active={s.id === activeId} {...rowProps} />)}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
