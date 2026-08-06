# AI Agent Application - Complete User Guide

## 📋 Table of Contents
1. [Overview](#overview)
2. [Getting API Keys](#getting-api-keys)
3. [Installation & Setup](#installation--setup)
4. [Configuration](#configuration)
5. [Starting the Application](#starting-the-application)
6. [Using the Application](#using-the-application)
7. [API Endpoints](#api-endpoints)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This AI Agent application helps you build software by using AI to:
- **Plan** - Create implementation plans
- **Implement** - Write code automatically
- **Execute** - Run code in isolated Docker containers
- **Validate** - Check if the application works

**Supported LLM Providers:**
- ✅ **Groq** (Recommended - Fast & Free tier available)
- ✅ **OpenAI** (GPT-4, GPT-3.5)
- ✅ **Anthropic** (Claude)
- ✅ **Ollama** (Local models)

---

## Getting API Keys

### Option 1: Groq (Recommended - FREE!)

**Why Groq?**
- ⚡ **Fastest inference** (up to 10x faster than others)
- 💰 **Free tier** with generous limits
- 🎯 **Great for coding** (Llama 3.3 70B model)

**How to Get Groq API Key:**

1. **Visit Groq Console**
   - Go to: https://console.groq.com/

2. **Sign Up / Log In**
   - Click "Sign Up" (free account)
   - Use Google, GitHub, or email

3. **Create API Key**
   - Go to "API Keys" section
   - Click "Create API Key"
   - Give it a name (e.g., "myaiagent")
   - Copy the key (starts with `gsk_`)

4. **Save Your Key**
   ```
   gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
   ⚠️ **Important:** Save this key securely - you won't see it again!

**Free Tier Limits:**
- 30 requests per minute
- 14,400 requests per day
- More than enough for development!

---

### Option 2: OpenAI

**How to Get OpenAI API Key:**

1. Visit: https://platform.openai.com/
2. Sign up / Log in
3. Go to "API Keys" section
4. Click "Create new secret key"
5. Copy the key (starts with `sk-`)

**Cost:** Pay-as-you-go (GPT-4: ~$0.03 per 1K tokens)

---

### Option 3: Anthropic (Claude)

**How to Get Anthropic API Key:**

1. Visit: https://console.anthropic.com/
2. Sign up / Log in
3. Go to "API Keys"
4. Create new key
5. Copy the key (starts with `sk-ant-`)

**Cost:** Pay-as-you-go (Claude: ~$0.015 per 1K tokens)

---

### Option 4: Ollama (Local - FREE!)

**How to Use Ollama:**

1. **Install Ollama**
   ```bash
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # macOS
   brew install ollama
   
   # Or download from: https://ollama.com/download
   ```

2. **Start Ollama**
   ```bash
   ollama serve
   ```

3. **Pull a Model**
   ```bash
   # Recommended for coding
   ollama pull qwen2.5-coder:7b
   
   # Or larger model (needs 16GB+ RAM)
   ollama pull qwen2.5-coder:32b
   ```

**Pros:** Free, private, no API key needed
**Cons:** Slower, requires good hardware

---

## Installation & Setup

### Prerequisites

1. **Docker & Docker Compose**
   ```bash
   # Check if installed
   docker --version
   docker compose version
   ```
   If not installed: https://docs.docker.com/get-docker/

2. **Python 3.12+**
   ```bash
   python3 --version
   ```

3. **Node.js 18+**
   ```bash
   node --version
   npm --version
   ```

### Step 1: Clone/Navigate to Project

```bash
cd "/media/aashikant/GAME Volume/aicode/myaiagent"
```

### Step 2: Start Infrastructure

```bash
# Start PostgreSQL and Redis
docker compose up -d

# Verify they're running
docker compose ps
```

You should see:
- `myaiagent-postgres-1` - Running
- `myaiagent-redis-1` - Running

### Step 3: Setup Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python migrations/run_migrations.py
```

### Step 4: Setup Frontend

```bash
cd ../frontend

# Install dependencies
npm install
```

---

## Configuration

### Method 1: Environment Variables (Recommended)

Create/edit `backend/.env` file:

```bash
cd backend
nano .env  # or use any text editor
```

**For Groq (Recommended):**
```env
# LLM Configuration
DEFAULT_LLM_PROVIDER=groq
DEFAULT_LLM_MODEL=groq/llama-3.3-70b-versatile
GROQ_API_KEY=gsk_your_actual_key_here

# Database (default values)
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_USER=langgraph
POSTGRES_PASSWORD=langgraph_password
POSTGRES_DB=agent_state

# Redis (default values)
REDIS_HOST=localhost
REDIS_PORT=6379

# Server
DEBUG=false
HOST=0.0.0.0
PORT=8001

# Secrets Encryption (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SECRETS_FERNET_KEY=your_generated_key_here

# Sandbox
SANDBOX_CLEANUP_INTERVAL=3600
```

**For OpenAI:**
```env
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-your_actual_key_here
```

**For Anthropic:**
```env
DEFAULT_LLM_PROVIDER=anthropic
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-your_actual_key_here
```

**For Ollama (Local):**
```env
DEFAULT_LLM_PROVIDER=ollama
DEFAULT_LLM_MODEL=ollama/qwen2.5-coder:7b
OLLAMA_BASE_URL=http://localhost:11434
# No API key needed!
```

### Method 2: Using the Secrets API (More Secure)

You can store API keys in the encrypted database instead:

```bash
# Start the backend first (see next section)

# Then store your key via API
curl -X POST http://localhost:8001/api/secrets \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "secret": "gsk_your_actual_key_here"
  }'
```

---

## Starting the Application

### Terminal 1: Start Backend

```bash
cd backend
source venv/bin/activate
PORT=8001 python main.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Terminal 2: Start Frontend

```bash
cd frontend
npm run dev
```

You should see:
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
```

### Access the Application

Open your browser and go to:
```
http://localhost:5173
```

---

## Using the Application

### 1. Web Interface (Frontend)

**Main Features:**

1. **Chat Interface**
   - Type your request (e.g., "Create a todo app with React")
   - The agent will plan, implement, and execute the code
   - See real-time progress in the chat

2. **Sandbox Panel**
   - View running Docker containers
   - See resource usage (CPU, memory)
   - Pause/Resume/Delete containers
   - View generated files

3. **Settings**
   - Manage LLM profiles
   - Switch between different models
   - Configure API keys

### 2. API Usage (Programmatic)

#### Create a Session

```bash
curl -X POST http://localhost:8001/api/agent/sessions \
  -H "Content-Type: application/json"
```

Response:
```json
{
  "session_id": "abc-123-def",
  "profile_id": "uuid-here",
  "profile": {
    "provider": "groq",
    "model": "groq/llama-3.3-70b-versatile",
    "temperature": 0.2
  }
}
```

#### Send a Message via WebSocket

```javascript
// JavaScript example
const ws = new WebSocket('ws://localhost:8001/api/agent/ws');

ws.onopen = () => {
  ws.send(JSON.stringify({
    session_id: 'abc-123-def',
    message: 'Create a simple calculator app'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Agent:', data);
};
```

#### List Conversations

```bash
curl http://localhost:8001/api/conversations
```

#### Manage LLM Profiles

```bash
# List profiles
curl http://localhost:8001/api/settings/llm-profiles

# Create new profile
curl -X POST http://localhost:8001/api/settings/llm-profiles \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "groq",
    "model": "groq/llama-3.3-70b-versatile",
    "temperature": 0.2,
    "max_tokens": 4096,
    "is_default": true
  }'

# Set as default
curl -X POST http://localhost:8001/api/settings/llm-profiles/{id}/default
```

---

## API Endpoints

### Agent Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/api/agent/sessions` | Create new session |
| WS | `/api/agent/ws` | WebSocket for streaming |
| GET | `/api/agent/health` | Agent health check |

### Sandbox Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/sandbox/{id}/status` | Get container status |
| GET | `/api/sandbox/{id}/health` | Check if app is running |
| GET | `/api/sandbox/{id}/files` | List generated files |
| GET | `/api/sandbox/{id}/files/read?path=` | Read a file |
| POST | `/api/sandbox/{id}/pause` | Pause container |
| POST | `/api/sandbox/{id}/resume` | Resume container |
| DELETE | `/api/sandbox/{id}` | Delete container |

### Settings Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | Get all settings |
| PUT | `/api/settings/{key}` | Update setting |
| POST | `/api/settings/reset` | Reset to defaults |
| GET | `/api/settings/llm-profiles` | List LLM profiles |
| POST | `/api/settings/llm-profiles` | Create profile |
| GET | `/api/settings/llm-profiles/{id}` | Get profile |
| PUT | `/api/settings/llm-profiles/{id}` | Update profile |
| DELETE | `/api/settings/llm-profiles/{id}` | Delete profile |
| POST | `/api/settings/llm-profiles/{id}/default` | Set as default |

### Secrets Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/secrets` | List secrets (masked) |
| GET | `/api/secrets/{provider}` | Get secret (masked) |
| POST | `/api/secrets` | Store secret |
| DELETE | `/api/secrets/{provider}` | Delete secret |
| POST | `/api/secrets/{provider}/test` | Test API key |

### Conversations Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/conversations` | List conversations |
| POST | `/api/conversations` | Create conversation |
| GET | `/api/conversations/{id}` | Get conversation |
| POST | `/api/conversations/{id}/pause` | Pause conversation |
| POST | `/api/conversations/{id}/resume` | Resume conversation |
| DELETE | `/api/conversations/{id}` | Delete conversation |

---

## Troubleshooting

### Issue: "GROQ_API_KEY not found"

**Solution:**
1. Check your `.env` file exists in `backend/` directory
2. Verify the key is correct (starts with `gsk_`)
3. Restart the backend server

```bash
cd backend
cat .env  # Check if key is there
source venv/bin/activate
PORT=8001 python main.py
```

### Issue: "Connection refused" to PostgreSQL

**Solution:**
```bash
# Check if PostgreSQL is running
docker compose ps

# If not running, start it
docker compose up -d

# Check logs
docker compose logs postgres
```

### Issue: "Port 8001 already in use"

**Solution:**
```bash
# Find what's using the port
lsof -i :8001

# Kill the process or use a different port
PORT=8002 python main.py
```

### Issue: Frontend can't connect to backend

**Solution:**
1. Check backend is running on port 8001
2. Check CORS settings in `backend/main.py`
3. Try accessing: http://localhost:8001/ (should return JSON)

### Issue: Ollama not working

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve

# Pull the model
ollama pull qwen2.5-coder:7b
```

### Issue: Docker containers not starting

**Solution:**
```bash
# Check Docker is running
docker ps

# Check Docker Compose
docker compose ps

# Restart services
docker compose down
docker compose up -d

# Check logs
docker compose logs
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Backend
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

---

## Quick Start Checklist

- [ ] Docker & Docker Compose installed
- [ ] Python 3.12+ installed
- [ ] Node.js 18+ installed
- [ ] Got API key from Groq (or other provider)
- [ ] Created `backend/.env` file with API key
- [ ] Started PostgreSQL & Redis: `docker compose up -d`
- [ ] Ran migrations: `python migrations/run_migrations.py`
- [ ] Installed backend deps: `pip install -r requirements.txt`
- [ ] Installed frontend deps: `npm install`
- [ ] Started backend: `PORT=8001 python main.py`
- [ ] Started frontend: `npm run dev`
- [ ] Opened browser: http://localhost:5173

---

## Example Usage

### Example 1: Create a Todo App

1. Open http://localhost:5173
2. Type in chat: "Create a todo app with React and local storage"
3. Watch the agent:
   - Plan the implementation
   - Write the code
   - Execute it in a sandbox
   - Validate it works
4. View the generated files in the Sandbox Panel
5. Access the running app (if applicable)

### Example 2: Using Different Models

```bash
# Switch to GPT-4
curl -X POST http://localhost:8001/api/settings/llm-profiles \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.2,
    "is_default": true
  }'

# Create new session (will use GPT-4)
curl -X POST http://localhost:8001/api/agent/sessions
```

### Example 3: Managing Secrets

```bash
# Store Groq key
curl -X POST http://localhost:8001/api/secrets \
  -H "Content-Type: application/json" \
  -d '{"provider": "groq", "secret": "gsk_..."}'

# Test the key
curl -X POST http://localhost:8001/api/secrets/groq/test

# List all secrets (masked)
curl http://localhost:8001/api/secrets
```

---

## Token Management & Context Optimization

The agent automatically manages token usage to prevent context overflow and optimize LLM calls across all operations.

### Automatic Features

**Token Counting & Budget Allocation:**
- Uses `tiktoken` for accurate token counting (with character-based fallback)
- Automatically allocates context window budget across:
  - System prompts (1,000 tokens)
  - Tools/functions (1,500 tokens)
  - Workspace context (2,000 tokens)
  - Conversation history (remaining budget)
  - Response buffer (varies by model)

**Intelligent Message Pruning:**
- Automatically prunes long conversation histories
- Preserves critical context (first and last messages)
- Summarizes middle messages when needed
- Logs warnings when usage exceeds 80% of budget

**Overflow Handling:**
- Aggressive pruning: Keeps first + last 3 messages when standard pruning isn't enough
- Hard truncation: Last resort for extremely long individual messages
- Automatically creates ultra-compact summaries of omitted content

### Monitoring Token Usage

Token metrics are automatically tracked in the agent state:

```python
{
  "token_count": 4500,              # Current token usage
  "total_tokens_processed": 25000,  # Total tokens across all LLM calls
  "total_pruning_events": 3,        # Number of times pruning occurred
  "total_overflow_events": 0,       # Number of overflow handling events
  "max_token_count_reached": 8000,  # Peak token usage in session
  "context_budget": {               # Budget allocation details
    "model": "gpt-4o",
    "max_tokens": 128000,
    "conversation": 121500,
    "workspace_context": 2000,
    "system_prompt": 1000,
    "tools": 1500
  }
}
```

### Performance

- **Token counting overhead**: <10ms per operation
- **Message pruning overhead**: <50ms per operation
- **No user intervention required**: All optimizations are automatic

### Best Practices

1. **Use models with larger context windows** for complex projects (GPT-4o, Claude 3.5 Sonnet recommended)
2. **Monitor logs** for frequent pruning events (may indicate conversations are too long)
3. **Break down large projects** into smaller sessions if you see frequent overflow events
4. **Check metrics** in the agent state to understand token consumption patterns

---

## Support & Resources

- **Documentation:** See `ARCHITECTURE.md` and `DEVELOPMENT.md`
- **API Docs:** http://localhost:8001/docs (when backend is running)
- **Groq Console:** https://console.groq.com/
- **OpenAI Platform:** https://platform.openai.com/
- **Anthropic Console:** https://console.anthropic.com/
- **Ollama:** https://ollama.com/

---

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use `.env` file** for local development
3. **Use Secrets API** for production
4. **Rotate keys regularly**
5. **Set up rate limiting** for production
6. **Use HTTPS** in production
7. **Keep dependencies updated**

---

## Next Steps

1. ✅ Get your API key (Groq recommended)
2. ✅ Configure `.env` file
3. ✅ Start the application
4. ✅ Try creating a simple app
5. 🚀 Build amazing things with AI!

**Happy coding! 🎉**
