from __future__ import annotations

import threading
import queue
from pathlib import Path
from tkinter import (
    Tk,
    Text,
    Entry,
    Button,
    Scrollbar,
    Frame,
    Label,
    StringVar,
    END,
    filedialog,
)

from .api_client import APIClient


class ChatApp:
    """Tkinter GUI for interacting with the LLM backend."""

    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("LLM Backend Chat")

        self.server_var = StringVar(value="http://localhost:8000")
        self.api_key_var = StringVar(value="")
        self.user_var = StringVar(value="default")
        self.session_var = StringVar(value="default")

        self._client = APIClient()
        self._queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self._build_ui()
        self.root.after(100, self._process_queue)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        top = Frame(self.root)
        top.pack(fill="x")

        Label(top, text="Server:").grid(row=0, column=0, sticky="w")
        Entry(top, textvariable=self.server_var, width=30).grid(row=0, column=1, sticky="ew")

        Label(top, text="API Key:").grid(row=0, column=2, sticky="w")
        Entry(top, textvariable=self.api_key_var, width=20).grid(row=0, column=3, sticky="ew")

        Label(top, text="User:").grid(row=1, column=0, sticky="w")
        Entry(top, textvariable=self.user_var, width=15).grid(row=1, column=1, sticky="ew")

        Label(top, text="Session:").grid(row=1, column=2, sticky="w")
        Entry(top, textvariable=self.session_var, width=15).grid(row=1, column=3, sticky="ew")

        self.chat_display = Text(self.root, wrap="word", height=20)
        self.chat_display.pack(fill="both", expand=True)

        scroll = Scrollbar(self.chat_display)
        scroll.pack(side="right", fill="y")
        self.chat_display.config(yscrollcommand=scroll.set)
        scroll.config(command=self.chat_display.yview)

        bottom = Frame(self.root)
        bottom.pack(fill="x")

        self.msg_entry = Entry(bottom)
        self.msg_entry.pack(side="left", fill="x", expand=True)
        self.msg_entry.bind("<Return>", lambda _: self.send_message())

        Button(bottom, text="Send", command=self.send_message).pack(side="left")
        Button(bottom, text="Upload", command=self.upload_file).pack(side="left")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _update_client(self) -> None:
        self._client = APIClient(self.server_var.get(), self.api_key_var.get() or None)

    def send_message(self) -> None:
        prompt = self.msg_entry.get().strip()
        if not prompt:
            return
        self.msg_entry.delete(0, END)
        self.chat_display.insert(END, f"You: {prompt}\n")
        self.chat_display.see(END)
        self._update_client()
        thread = threading.Thread(target=self._stream_prompt, args=(prompt,), daemon=True)
        thread.start()

    def _stream_prompt(self, prompt: str) -> None:
        try:
            for part in self._client.stream_chat(
                self.user_var.get(), self.session_var.get(), prompt
            ):
                self._queue.put(("assistant", part))
        except Exception as exc:  # pragma: no cover - runtime errors
            self._queue.put(("error", str(exc)))

    def upload_file(self) -> None:
        path = filedialog.askopenfilename()
        if path:
            self._update_client()
            thread = threading.Thread(target=self._upload_file, args=(Path(path),), daemon=True)
            thread.start()

    def _upload_file(self, path: Path) -> None:
        try:
            vm_path = self._client.upload_document(
                self.user_var.get(), self.session_var.get(), str(path)
            )
            self._queue.put(("info", f"Uploaded {path.name} -> {vm_path}"))
        except Exception as exc:  # pragma: no cover - runtime errors
            self._queue.put(("error", str(exc)))

    # ------------------------------------------------------------------
    # Queue processing
    # ------------------------------------------------------------------
    def _process_queue(self) -> None:
        while True:
            try:
                kind, msg = self._queue.get_nowait()
            except queue.Empty:
                break
            if kind == "assistant":
                self.chat_display.insert(END, msg)
            else:
                prefix = "INFO" if kind == "info" else "ERROR"
                self.chat_display.insert(END, f"[{prefix}] {msg}\n")
            self.chat_display.see(END)
        self.root.after(100, self._process_queue)


def main() -> None:
    root = Tk()
    ChatApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
