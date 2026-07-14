import { useRef, useState } from "react";

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  busy: boolean;
}

export default function MessageInput({ onSend, onStop, busy }: Props) {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  function submit() {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue("");
    if (taRef.current) taRef.current.style.height = "auto";
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autoGrow() {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  return (
    <div className="px-4 pb-4 pt-2">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 bg-bubble rounded-3xl px-4 py-3
                        border border-white/10 focus-within:border-white/25">
          <textarea
            ref={taRef}
            rows={1}
            value={value}
            placeholder="Ask about transaction database records…"
            onChange={(e) => {
              setValue(e.target.value);
              autoGrow();
            }}
            onKeyDown={onKeyDown}
            className="flex-1 bg-transparent resize-none outline-none text-[15px]
                       text-neutral-100 placeholder-neutral-500 max-h-[200px]"
          />
          {busy ? (
            <button
              onClick={onStop}
              className="shrink-0 h-8 w-8 rounded-full bg-white text-black
                         flex items-center justify-center hover:opacity-80"
              title="Stop"
            >
              ■
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!value.trim()}
              className="shrink-0 h-8 w-8 rounded-full bg-white text-black
                         flex items-center justify-center disabled:opacity-30
                         hover:opacity-80"
              title="Send"
            >
              ↑
            </button>
          )}
        </div>
        <p className="text-center text-[11px] text-neutral-500 mt-2">
          Answers come from the SQLite database via MCP tools.
        </p>
      </div>
    </div>
  );
}
