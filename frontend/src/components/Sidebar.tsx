import type { Conversation } from "../types";

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  open,
  onClose,
}: Props) {
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed md:static z-30 h-full w-64 bg-sidebar flex flex-col
          transition-transform duration-200
          ${open ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
      >
        <div className="p-3">
          <button
            onClick={onNew}
            className="w-full flex items-center gap-2 rounded-lg border
                       border-white/15 px-3 py-2 text-sm text-neutral-100
                       hover:bg-white/10 transition"
          >
            <span className="text-lg leading-none">＋</span> New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-1">
          {conversations.length === 0 && (
            <p className="text-xs text-neutral-500 px-3 py-2">
              No conversations yet.
            </p>
          )}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`group flex items-center rounded-lg px-3 py-2 text-sm
                cursor-pointer transition
                ${c.id === activeId ? "bg-white/10" : "hover:bg-white/5"}`}
              onClick={() => onSelect(c.id)}
            >
              <span className="flex-1 truncate text-neutral-200">
                {c.title}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-neutral-400
                           hover:text-red-400 transition ml-2"
                title="Delete"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <div className="p-3 text-xs text-neutral-500 border-t border-white/10">
          Transaction Analytics · local-first
        </div>
      </aside>
    </>
  );
}
