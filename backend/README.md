# OS Agent Backend API

This directory contains the FastAPI backend for the OS Agent web interface.

## Setup and Running

1.  **Navigate to the backend directory:**
    ```bash
    cd backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: A `requirements.txt` file should be generated. For now, dependencies are `fastapi uvicorn python-multipart pydantic`)*

4.  **Run the FastAPI application:**
    ```bash
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```
    The API will be accessible at `http://localhost:8000`.

## API Endpoints

*   `GET /`: Welcome message.
*   `POST /api/chat`: Endpoint for sending chat messages to the agent.
    *   Request body: `{"message": "your message", "session_id": "optional_session_id"}`
    *   Response body: `{"response": "agent's reply", "session_id": "optional_session_id", "timestamp": "YYYY-MM-DD HH:MM:SS"}`
*   `GET /api/stream_url`: (Placeholder) Returns a mock URL for the VM video stream.

## Project Structure

*   `main.py`: The main FastAPI application file, including endpoint definitions and CORS configuration.
*   `agent_logic/`: Directory for the business logic of the OS agent.
    *   `agent_service.py`: Contains functions for processing commands and interacting with the (mocked) OS agent.
*   `venv/`: Python virtual environment (ignored by git).
*   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
*   `requirements.txt`: (To be generated) Lists project dependencies.

## To Do / Future Enhancements

*   Replace mock agent logic in `agent_service.py` with actual OS interaction capabilities.
*   Implement robust session management.
*   Develop the VM video streaming functionality.
*   Add authentication and authorization if needed.
*   Expand error handling and logging.
```
