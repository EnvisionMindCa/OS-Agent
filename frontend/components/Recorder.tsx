"use client";
import { useEffect } from "react";
import { useReactMediaRecorder } from "react-media-recorder";

interface Props {
  onSave: (file: File) => void;
}

export default function Recorder({ onSave }: Props) {
  const {
    status,
    startRecording,
    stopRecording,
    mediaBlobUrl,
    clearBlobUrl,
  } = useReactMediaRecorder({ audio: true });

  useEffect(() => {
    if (!mediaBlobUrl) return;
    (async () => {
      const blob = await fetch(mediaBlobUrl).then((r) => r.blob());
      const file = new File([blob], `recording-${Date.now()}.webm`, {
        type: blob.type,
      });
      onSave(file);
      clearBlobUrl();
    })();
  }, [mediaBlobUrl, onSave, clearBlobUrl]);

  return (
    <>
      <button
        type="button"
        onClick={status === "recording" ? stopRecording : startRecording}
        className="px-4 py-2 rounded-md bg-red-600/80"
      >
        {status === "recording" ? "Stop" : "Record"}
      </button>
      {status !== "idle" && (
        <span className="self-center text-sm text-gray-300 ml-2">{status}</span>
      )}
    </>
  );
}
