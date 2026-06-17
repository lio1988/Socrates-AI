#!/usr/bin/env python3
"""
API Documentation and Usage Guide for Socratic Dialog FastAPI Backend
"""

# ============================================================================
# API ENDPOINTS DOCUMENTATION
# ============================================================================

"""
BASE URL: http://localhost:8000

1. HEALTH CHECK
───────────────────────────────────────────────────────────────────────────

GET /health
  Description: Check server health and configured models
  
  Response (200):
  {
    "status": "healthy",
    "configured_models": ["claude", "grok", "gemini", "chatgpt"],
    "timestamp": "2026-06-17T12:34:56.789012"
  }


2. START A NEW DIALOG SESSION
───────────────────────────────────────────────────────────────────────────

POST /dialog/start
  
  Request Body:
  {
    "topic": "Τι είναι η αλήθεια;",  // Required, 1-500 chars
    "rounds": 8,                      // Optional, default 8, max 20
    "mode": "socratic",               // Optional, one of: socratic, debate, consensus
    "speed": "normal",                // Optional, one of: very_slow, slow, normal, fast, very_fast
    "summary_mode": "every"           // Optional, one of: none, every, half
  }
  
  Response (200):
  {
    "session_id": "dialog_a1b2c3d4e5f6",
    "status": "started",
    "topic": "Τι είναι η αλήθεια;",
    "rounds": 8,
    "mode": "socratic",
    "message": "Dialog session dialog_a1b2c3d4e5f6 started. Use /dialog/dialog_a1b2c3d4e5f6 to monitor progress."
  }
  
  Errors:
  - 500: No API keys configured
  - 500: Fewer than 2 models available


3. GET DIALOG STATUS
───────────────────────────────────────────────────────────────────────────

GET /dialog/{session_id}
  
  Response (200):
  {
    "session_id": "dialog_a1b2c3d4e5f6",
    "topic": "Τι είναι η αλήθεια;",
    "rounds": 8,
    "mode": "socratic",
    "current_round": 3,
    "status": "running",  // One of: initialized, running, completed, error
    "history": [
      {
        "round": 1,
        "model_id": "claude",
        "content": "Σας ρωτώ...",
        "is_socratic": true,
        "timestamp": "2026-06-17T12:34:56.789012"
      },
      ...
    ],
    "scores": {
      "claude": 15,
      "grok": 12,
      "gemini": 18,
      "chatgpt": 10
    }
  }
  
  Errors:
  - 404: Session not found


4. STREAM DIALOG UPDATES (Server-Sent Events)
───────────────────────────────────────────────────────────────────────────

GET /dialog/{session_id}/stream
  
  Description: Real-time streaming of dialog events via SSE
  Content-Type: text/event-stream
  
  Events:
  - "turn": New dialog turn received
  - "status": Status and scores update
  - "complete": Dialog finished
  
  Example response stream:
  data: {"event":"turn","turn":{"round":1,"model_id":"claude",...}}
  
  data: {"event":"status","status":"running","scores":{...}}
  
  data: {"event":"complete","status":"completed"}


5. EXPORT DIALOG
───────────────────────────────────────────────────────────────────────────

GET /dialog/{session_id}/export?format=json
  
  Query Parameters:
  - format: "json" (default) or "markdown"
  
  Response (200):
  {
    "topic": "Τι είναι η αλήθεια;",
    "mode": "socratic",
    "rounds": 8,
    "timestamp": "2026-06-17T12:34:56.789012",
    "history": [
      {
        "round": 1,
        "model_id": "claude",
        "content": "...",
        "is_socratic": true,
        "timestamp": "2026-06-17T12:34:56.789012"
      },
      ...
    ],
    "scores": {
      "claude": 15,
      "grok": 12,
      "gemini": 18,
      "chatgpt": 10
    }
  }
  
  Errors:
  - 404: Session not found


6. DELETE DIALOG SESSION
───────────────────────────────────────────────────────────────────────────

DELETE /dialog/{session_id}
  
  Response (200):
  {
    "session_id": "dialog_a1b2c3d4e5f6",
    "status": "deleted",
    "message": "Dialog session dialog_a1b2c3d4e5f6 has been deleted"
  }
  
  Errors:
  - 404: Session not found


7. LIST ACTIVE DIALOGS
───────────────────────────────────────────────────────────────────────────

GET /dialog/list/active
  
  Response (200):
  {
    "count": 2,
    "sessions": [
      {
        "session_id": "dialog_a1b2c3d4e5f6",
        "topic": "Τι είναι η αλήθεια;",
        "status": "running",
        "created_at": "2026-06-17T12:34:56.789012",
        "rounds": 8
      },
      ...
    ]
  }


============================================================================
EXAMPLE WORKFLOWS
============================================================================

WORKFLOW 1: Simple Dialog with Polling
─────────────────────────────────────────

1. Start dialog:
   POST /dialog/start
   {
     "topic": "Τι είναι ο νους;",
     "rounds": 4,
     "mode": "socratic"
   }
   → Get session_id: "dialog_abc123"

2. Poll for status (repeat until "completed"):
   GET /dialog/dialog_abc123
   → Check current_round and status

3. Export results:
   GET /dialog/dialog_abc123/export


WORKFLOW 2: Real-Time Streaming Dialog
─────────────────────────────────────────

1. Start dialog (same as above)

2. Connect to SSE stream:
   GET /dialog/dialog_abc123/stream
   
   Listen for events:
   - "turn" → Display new dialog turn
   - "status" → Update scores
   - "complete" → Show final results

3. Export when done


WORKFLOW 3: Multiple Concurrent Dialogs
─────────────────────────────────────────

1. Start multiple dialogs (get different session_ids)

2. List all active:
   GET /dialog/list/active

3. Monitor each with:
   GET /dialog/{session_id}

4. Export when needed


============================================================================
CURL EXAMPLES
============================================================================

# Check health
curl http://localhost:8000/health

# Start a dialog
curl -X POST http://localhost:8000/dialog/start \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Τι είναι η αγάπη;",
    "rounds": 6,
    "mode": "socratic",
    "speed": "normal"
  }'

# Get dialog status
curl http://localhost:8000/dialog/dialog_a1b2c3d4e5f6

# Stream events
curl http://localhost:8000/dialog/dialog_a1b2c3d4e5f6/stream

# Export dialog
curl http://localhost:8000/dialog/dialog_a1b2c3d4e5f6/export > dialog.json

# Delete dialog
curl -X DELETE http://localhost:8000/dialog/dialog_a1b2c3d4e5f6

# List active dialogs
curl http://localhost:8000/dialog/list/active


============================================================================
ENVIRONMENT VARIABLES
============================================================================

Required (set at least 2):
  ANTHROPIC_API_KEY     - Claude API key (Anthropic)
  XAI_API_KEY           - Grok API key (xAI)
  GOOGLE_API_KEY        - Gemini API key (Google)
  OPENAI_API_KEY        - ChatGPT API key (OpenAI)

Example .env file:
  ANTHROPIC_API_KEY=sk-ant-xxx
  XAI_API_KEY=xai-xxx
  GOOGLE_API_KEY=AIzaSyxxx
  OPENAI_API_KEY=sk-xxx


============================================================================
INSTALLATION & RUNNING
============================================================================

1. Install dependencies:
   pip install -r requirements.txt

2. Set up environment variables:
   cp .env.example .env
   # Edit .env with your API keys

3. Run the server:
   python main.py
   
   Or with custom host/port:
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

4. Access API documentation:
   http://localhost:8000/docs          (Swagger UI)
   http://localhost:8000/redoc         (ReDoc)


============================================================================
RESPONSE CODES
============================================================================

200 OK              - Request successful
400 Bad Request     - Invalid request data
404 Not Found       - Session or resource not found
500 Server Error    - Internal error (check logs)


============================================================================
NOTES
============================================================================

- Sessions run asynchronously in background tasks
- Multiple dialogs can run concurrently
- Dialog updates are streamed in real-time via SSE
- Sessions persist in memory until deleted
- Maximum 20 rounds per dialog
- At least 2 models must be configured
"""
