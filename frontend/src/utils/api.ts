export interface ChatRequest {
  user: string;
  session: string;
  prompt: string;
}

export async function* streamChat(
  req: ChatRequest
): AsyncGenerator<string> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}/chat/stream`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  });

  if (!res.ok || !res.body) {
    throw new Error('API request failed');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    yield decoder.decode(value);
  }
}
