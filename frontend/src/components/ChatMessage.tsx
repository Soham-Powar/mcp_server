import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../types";

interface Props {
  message: Message;
  streaming?: boolean;
}

export default function ChatMessage({ message, streaming }: Props) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] md:max-w-[75%] rounded-2xl px-4 py-3 text-[15px]
          ${isUser ? "bg-bubble text-neutral-100" : "bg-transparent text-neutral-100"}`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        ) : (
          <div className={`markdown ${streaming ? "cursor" : ""}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || (streaming ? "" : "…")}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
