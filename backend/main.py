from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time
from agent_logic.agent_service import process_user_command # Correctly import the service

# --- Pydantic Models ---
class ChatMessageRequest(BaseModel):
    message: str
    session_id: str | None = None

class ChatMessageResponse(BaseModel):
    response: str
    session_id: str | None = None
    timestamp: str

# --- FastAPI App Initialization ---
app = FastAPI(
    title="OS Agent API",
    description="API for interacting with the OS Agent.",
    version="0.1.0",
)

# --- CORS Middleware ---
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---
@app.get("/")
async def read_root():
    return {"message": "Welcome to the OS Agent API. Use the /api/chat endpoint to interact."}

@app.post("/api/chat", response_model=ChatMessageResponse)
async def chat_with_agent(request: ChatMessageRequest):
    """
    Receives a user message, processes it using the agent_service,
    and returns the agent's response.
    """
    print(f"Received message: {request.message} for session: {request.session_id}") # Server-side log

    # Use the imported agent service to process the message
    agent_reply = await process_user_command(request.message, request.session_id)

    return ChatMessageResponse(
        response=agent_reply,
        session_id=request.session_id,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
    )

@app.get("/api/stream_url")
async def get_stream_url():
    """
    Returns the URL for the VM video stream.
    (This is a placeholder - actual implementation will depend on the streaming solution)
    """
    return {"url": "rtsp://example.com/live/stream1", "type": "RTSP_placeholder"}

if __name__ == "__main__":
    import uvicorn
    # To run from command line: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
