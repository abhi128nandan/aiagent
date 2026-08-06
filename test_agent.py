#!/usr/bin/env python3
"""
Test script to verify the AI agent can build applications
"""
import asyncio
import websockets
import json
import requests

BACKEND_URL = "http://localhost:8000"

async def test_build_todo_app():
    """Test building a To-Do application"""
    
    # Step 1: Create a session
    print("📝 Creating session...")
    response = requests.post(f"{BACKEND_URL}/api/agent/sessions")
    session_data = response.json()
    session_id = session_data['session_id']
    print(f"✅ Session created: {session_id}")
    print(f"   Using LLM: {session_data['profile']['provider']} - {session_data['profile']['model']}")
    
    # Step 2: Connect to WebSocket
    ws_url = "ws://localhost:8000/api/agent/ws"
    print(f"\n🔌 Connecting to WebSocket at {ws_url}...")
    
    srs_text = """Build a simple To-Do application with these features:

1. Task Management:
   - Add new tasks with title and description
   - Mark tasks as complete
   - Delete tasks
   - List all tasks

2. Tech Stack:
   - Frontend: Simple HTML + CSS + JavaScript
   - Backend: Python Flask
   - Database: SQLite

3. Requirements:
   - Create a single-page application
   - Store tasks in SQLite database
   - RESTful API endpoints
   - Responsive design

Build the complete application, install dependencies, and run it on port 5000."""

    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Connected to WebSocket")
            
            # Send the build request
            print(f"\n🚀 Sending build request for session {session_id}...")
            await websocket.send(json.dumps({
                "session_id": session_id,
                "action": "start",
                "message": srs_text,
                "chat_mode": "build",
                "locked_files": [],
                "last_seq": 0
            }))
            print("✅ Request sent")
            
            print("\n📡 Streaming agent responses:\n")
            print("=" * 80)
            
            # Receive and print responses
            message_count = 0
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_count += 1
                    event_type = data.get('type')
                    node = data.get('node')
                    chunk = data.get('chunk', '')
                    
                    if event_type == 'ping':
                        await websocket.send(json.dumps({"type": "pong", "ts": data.get("ts")}))
                    elif event_type == 'on_chat_model_stream' and chunk:
                        print(chunk, end='', flush=True)
                    elif event_type == 'on_chain_start':
                        print(f"\n[Node Start: {node}]")
                    elif event_type == 'on_chain_end':
                        print(f"\n[Node Complete: {node}]")
                    elif event_type == 'error':
                        print(f"\n❌ ERROR: {data.get('message')}")
                        break
                        
                except json.JSONDecodeError:
                    print(f"Raw message: {message}")
                    
            print("\n" + "=" * 80)
            print(f"\n✅ WebSocket connection closed. Received {message_count} messages")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Backend is running: PORT=8000 python main.py")
        print("  2. GROQ_API_KEY is set in backend/.env")
        print("  3. Docker is running for sandbox")

if __name__ == "__main__":
    print("🤖 AI Agent Application Builder Test")
    print("=" * 80)
    asyncio.run(test_build_todo_app())
