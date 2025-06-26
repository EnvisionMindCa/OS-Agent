"use client";
import { useState, useEffect, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { useAgentChat } from "@/lib/useAgentChat";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { ModeToggle } from "@/components/theme-provider";
import { Paperclip, Send, Settings2, User, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Home() {
  const searchParams = useSearchParams();
  const initialSession = searchParams.get("session") || "main";
  const { messages, sendMessage, uploadFile, thinking } = useAgentChat({
    session: initialSession,
  });
  const [input, setInput] = useState("");
  const [sessionInput, setSessionInput] = useState(initialSession);
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageInputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    messageInputRef.current?.focus();
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text && !file) return; // Allow sending file without text

    if (file) {
      uploadFile(file, text || undefined); // Pass text as optional caption
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = ""; // Reset file input
      }
    } else if (text) {
      sendMessage(text);
    }
    setInput("");
  };

  const handleSessionUpdate = () => {
    const s = sessionInput.trim();
    if (!s) return;
    const url = new URL(window.location.href);
    url.searchParams.set("session", s);
    window.location.href = url.toString(); // This will cause a page reload
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files ? e.target.files[0] : null;
    setFile(selectedFile);
     // If there's text and a file, send immediately or wait for send button?
    // For now, we'll let the user click send.
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="flex flex-col h-screen bg-background text-foreground">
      <header className="p-4 flex flex-col sm:flex-row items-center justify-between gap-2 border-b shrink-0">
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Input
            type="text"
            placeholder="Session ID"
            value={sessionInput}
            onChange={(e) => setSessionInput(e.target.value)}
            className="flex-grow sm:flex-grow-0 sm:w-48"
          />
          <Button onClick={handleSessionUpdate} variant="outline" className="shrink-0">
            <Settings2 className="mr-2 h-4 w-4" /> Set Session
          </Button>
        </div>
        <div className="shrink-0">
          <ModeToggle />
        </div>
      </header>

      <main className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              "flex items-start gap-3 max-w-[85%] md:max-w-[75%] animate-in",
              m.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
            )}
          >
            {m.role === "user" ? (
              <User className="w-6 h-6 text-primary mt-1 shrink-0" />
            ) : (
              <Bot className="w-6 h-6 text-secondary-foreground mt-1 shrink-0" />
            )}
            <Card
              className={cn(
                "rounded-xl shadow-md",
                m.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-secondary-foreground"
              )}
            >
              <CardContent className="p-3 whitespace-pre-wrap break-words">
                {m.file ? (
                  <a
                    href={m.file.url}
                    download={m.file.name}
                    className="underline hover:text-blue-300 flex items-center gap-2"
                  >
                    <Paperclip className="w-4 h-4" />
                    {m.file.name}
                  </a>
                ) : null}
                {m.content && <div>{m.content}</div>}
              </CardContent>
            </Card>
          </div>
        ))}
        {thinking && (
          <div className="flex items-start gap-3 max-w-[85%] md:max-w-[75%] mr-auto">
             <Bot className="w-6 h-6 text-secondary-foreground mt-1 shrink-0" />
             <Card className="bg-secondary text-secondary-foreground rounded-xl shadow-md">
                <CardContent className="p-3">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-pulse delay-75"></div>
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-pulse delay-150"></div>
                    <div className="w-2 h-2 bg-muted-foreground rounded-full animate-pulse delay-300"></div>
                  </div>
                </CardContent>
             </Card>
          </div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="p-4 border-t shrink-0">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <Button type="button" variant="outline" size="icon" onClick={triggerFileInput}>
            <Paperclip className="h-5 w-5" />
            <span className="sr-only">Attach file</span>
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
          />
          <Input
            type="text"
            placeholder={file ? `Attach: ${file.name}` : "Type a message..."}
            ref={messageInputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="flex-1"
            disabled={thinking}
          />
          <Button type="submit" size="icon" disabled={thinking || (!input.trim() && !file)}>
            <Send className="h-5 w-5" />
            <span className="sr-only">Send message</span>
          </Button>
        </form>
        {file && (
          <div className="mt-2 text-sm text-muted-foreground">
            Selected file: {file.name}{" "}
            <Button variant="link" size="sm" onClick={() => { setFile(null); if(fileInputRef.current) fileInputRef.current.value = "";}} className="p-0 h-auto">
              Remove
            </Button>
          </div>
        )}
        <div className="mt-2 flex flex-wrap gap-2">
          {["What can you do?", "Explain this code...", "Suggest a refactor for..."].map((suggestion) => (
            <Button
              key={suggestion}
              variant="outline"
              size="sm"
              onClick={() => {
                setInput(suggestion);
                // Optionally, you could auto-submit here:
                // sendMessage(suggestion);
                // setInput("");
              }}
              disabled={thinking}
              className="text-xs"
            >
              {suggestion}
            </Button>
          ))}
        </div>
      </footer>
    </div>
  );
}
