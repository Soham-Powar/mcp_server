import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "./components/Sidebar";
import ModelSelector from "./components/ModelSelector";
import ChatMessage from "./components/ChatMessage";
import MessageInput from "./components/MessageInput";
import { fetchModels, streamChat } from "./api";
import type { Conversation, Message } from "./types";

const STORAGE_KEY = "upi-analytics-conversations";

const SAMPLE_PROMPTS = [
  "What was the total spending last month?",
  "What are the top merchants by volume?",
  "Show the biggest transaction details.",
  "How much amount went to shopping?",
  "What was the monthly spending trend over the last six months?",
  "How many failed transactions occurred in June?",
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function loadConversations(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

export default function App() {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations);
  const [activeId, setActiveId] = useState<string | null>(
    () => loadConversations()[0]?.id ?? null
  );
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("");
  const [loadingModels, setLoadingModels] = useState(true);
  const [modelError, setModelError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? null,
    [conversations, activeId]
  );

  // Persist conversations.
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  // Discover models on mount.
  useEffect(() => {
    fetchModels()
      .then((m) => {
        setModels(m);
        setModel((prev) => prev || m[0] || "");
      })
      .catch((e) => setModelError(e.message))
      .finally(() => setLoadingModels(false));
  }, []);

  // Autoscroll on new content.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [active?.messages]);

  function newConversation(): string {
    const conv: Conversation = {
      id: uid(),
      title: "New chat",
      messages: [],
      model: model,
      createdAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    return conv.id;
  }

  function updateConversation(id: string, fn: (c: Conversation) => Conversation) {
    setConversations((prev) => prev.map((c) => (c.id === id ? fn(c) : c)));
  }

  function deleteConversation(id: string) {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) setActiveId(null);
  }

  async function send(text: string) {
    if (!model) {
      setModelError("No model selected. Is Ollama running?");
      return;
    }
    let convId = activeId;
    if (!convId) convId = newConversation();

    const userMsg: Message = { role: "user", content: text };

    // Append user message + empty assistant placeholder.
    updateConversation(convId, (c) => ({
      ...c,
      title: c.messages.length === 0 ? text.slice(0, 40) : c.title,
      messages: [...c.messages, userMsg, { role: "assistant", content: "" }],
    }));

    // Build the message history to send (exclude the empty placeholder).
    const history = [
      ...(conversations.find((c) => c.id === convId)?.messages ?? []),
      userMsg,
    ];

    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        model,
        history,
        (chunk) => {
          updateConversation(convId!, (c) => {
            const msgs = [...c.messages];
            const last = msgs[msgs.length - 1];
            msgs[msgs.length - 1] = { ...last, content: last.content + chunk };
            return { ...c, messages: msgs };
          });
        },
        controller.signal
      );
    } catch (e: any) {
      if (e.name !== "AbortError") {
        updateConversation(convId!, (c) => {
          const msgs = [...c.messages];
          const last = msgs[msgs.length - 1];
          msgs[msgs.length - 1] = {
            ...last,
            content: last.content + `\n\n_Error: ${e.message}_`,
          };
          return { ...c, messages: msgs };
        });
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  const messages = active?.messages ?? [];
  const showWelcome = messages.length === 0;

  return (
    <div className="flex h-full">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={(id) => {
          setActiveId(id);
          setSidebarOpen(false);
        }}
        onNew={() => {
          newConversation();
          setSidebarOpen(false);
        }}
        onDelete={deleteConversation}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
          <button
            className="md:hidden text-neutral-300 text-xl"
            onClick={() => setSidebarOpen(true)}
          >
            ☰
          </button>
          <h1 className="text-sm font-medium text-neutral-200">UPI Analytics</h1>
          <div className="ml-auto">
            <ModelSelector
              models={models}
              selected={model}
              onChange={setModel}
              loading={loadingModels}
            />
          </div>
        </header>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {modelError && (
            <div className="mx-auto max-w-3xl mt-4 px-4">
              <div className="rounded-lg bg-red-500/10 border border-red-500/30
                              text-red-300 text-sm px-4 py-3">
                {modelError}
              </div>
            </div>
          )}

          {showWelcome ? (
            <div className="h-full flex flex-col items-center justify-center px-4">
              <h2 className="text-2xl font-semibold text-neutral-100 mb-2">
                Ask about transaction history
              </h2>
              <p className="text-neutral-400 text-sm mb-8 text-center">
                Natural-language analytics over UPI and IMPS database history.
              </p>
              <div className="grid sm:grid-cols-2 gap-3 w-full max-w-2xl">
                {SAMPLE_PROMPTS.map((p) => (
                  <button
                    key={p}
                    onClick={() => send(p)}
                    disabled={busy}
                    className="text-left rounded-xl border border-white/10 bg-bubble
                               px-4 py-3 text-sm text-neutral-200 hover:bg-white/10
                               transition disabled:opacity-50"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl px-4 py-6 space-y-5">
              {messages.map((m, i) => (
                <ChatMessage
                  key={i}
                  message={m}
                  streaming={busy && i === messages.length - 1 && m.role === "assistant"}
                />
              ))}
            </div>
          )}
        </div>

        <MessageInput onSend={send} onStop={stop} busy={busy} />
      </main>
    </div>
  );
}
