"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { sendAgentCommand } from "@/lib/agentApi";

interface SessionInfo {
  name: string;
  last_message: string;
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  useEffect(() => {
    sendAgentCommand<SessionInfo[]>("list_sessions_info")
      .then((res) => setSessions(res))
      .catch((err) => console.error(err));
  }, []);

  return (
    <div className="min-h-screen p-4 bg-gradient-to-br from-slate-900 to-gray-700 text-white">
      <h1 className="text-2xl font-bold mb-4">Sessions</h1>
      <ul className="space-y-2">
        {sessions.map((s) => (
          <li
            key={s.name}
            className="flex justify-between items-center p-3 rounded-md bg-white/10 border border-white/30"
          >
            <div>
              <span className="font-mono">{s.name}</span>
              {s.last_message && (
                <span className="ml-2 text-sm text-gray-300">
                  {s.last_message.slice(0, 60)}
                </span>
              )}
            </div>
            <Link
              href={`/?session=${encodeURIComponent(s.name)}`}
              className="px-3 py-1 rounded-md bg-blue-600/80"
            >
              Open
            </Link>
          </li>
        ))}
      </ul>
      <div className="mt-4">
        <Link href="/" className="underline">
          Back to Chat
        </Link>
      </div>
    </div>
  );
}
