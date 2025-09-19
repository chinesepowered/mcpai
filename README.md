# Viral Marketing Agent

AI-powered system that discovers trending Instagram content and instantly generates satirical, share-worthy videos.

## ✨ Key Features
- **Content Scraping** – Pull top-performing posts from Instagram accounts (primary via Bright Data MCP, fallback via Apify Instagram Scraper).
- **Idea Selection UI** – React dashboard lets you browse scraped posts and pick an idea to amplify.
- **AI Video Generation** – MiniMax MCP turns the selected idea into an auto-edited video (script, voice, visuals).
- **Download & Share** – Preview the result in-browser and export for rapid social distribution.

# run FastAPI server **from the backend directory**
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uvicorn main:app --reload
|--------------|------------|
| Backend      | Python 3.11 (FastAPI) |
| Frontend     | React 18 + Vite |
| AI / MCP     | MiniMax MCP (video generation) |
| Scraping     | Bright Data MCP (primary) • Apify Instagram Scraper (backup) |
| Auth / Config| dotenv for secrets |

## 🚀 Quick Start

### 1. Clone and prepare
```bash
git clone https://github.com/your-org/viral-marketing-agent.git
cd viral-marketing-agent
```

### 2. Environment variables  
Create a `.env` file at the project root:

```env
# MiniMax (video generation)
MINIMAX_API_KEY=your_minimax_key

# Bright Data (Instagram scraping)
BRIGHTDATA_API_TOKEN=your_brightdata_token

# Apify (backup scraper)
APIFY_API_TOKEN=your_apify_token
```

> **Never commit `.env`** – it is git-ignored.

### 3. Backend setup
```bash
# create virtual env
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# install deps
pip install -r backend/requirements.txt

# run FastAPI server
uvicorn backend.main:app --reload
```
Server starts at `http://localhost:8000`.

### 4. Frontend setup
```bash
cd frontend
npm install
npm run dev     # or: bun install && bun run dev
```
Frontend is now on `http://localhost:5173` (proxy to backend is pre-configured).

## ⚙️ MCP Server Commands
The backend wraps two MCP processes. They start automatically, but you can run them manually for troubleshooting:

```bash
# MiniMax
uvx minimax-mcp -y

# Bright Data
npx @brightdata/mcp
```

## 📚 Usage Guide

1. Open the web app.  
2. “Scrape New Ideas” to fetch latest viral posts from Instagram.  
3. Click any tile to view post details, caption & engagement stats.  
4. Press “Generate Video” → backend calls MiniMax MCP.  
5. Watch the preview; click “Download” to save MP4.

Typical turnaround is under 60 seconds.

## 📝 Development Scripts
```bash
# lint & format
ruff check .
black .

# run unit tests
pytest
```

## 🛠️ Troubleshooting

### `ModuleNotFoundError: No module named 'services'`
If you see this error when starting the backend it usually means the server is being
launched **from the project root** rather than inside the `backend` package.

Run the server like so:

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload
```

`main.py` uses relative imports (`from services import …`) that expect the working
directory to be `backend/`. Running from within that folder (or using
`python -m backend.main`) ensures the imports resolve correctly.

## 📄 License
MIT
