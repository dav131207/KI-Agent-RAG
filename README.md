# Professor Pepe

A clean, animated web AI assistant powered by **Google Gemini**. Chat with Professor Pepe, request random memes, rare pepes, or social media posts.

**Live Demo:** [https://professor-pepe-agent.onrender.com](https://professor-pepe-agent.onrender.com)

![stack](https://img.shields.io/badge/FastAPI-Python-green?logo=fastapi)
![stack](https://img.shields.io/badge/React-Vite-blue?logo=react)
![stack](https://img.shields.io/badge/Tailwind_CSS-38bdf8?logo=tailwindcss)

## Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/dav131207/zen-ai-agent)

Click the button above, connect your GitHub account, and fill in the environment variables when prompted.

## Features

- 💬 **Chat** with streaming responses, grounded in a Qdrant knowledge base (RAG)
- 🖼️ **Random Meme / Rare Pepe / Community Art / Social Media Post** commands
- 🔍 **Picture search in plain language**, any language — "ich suche einen Pepe der Fußball spielt" gets a shortlist of four
- 💧 **Watermark on every picture shown**; when saving, each picture offers *with watermark* or *original*
- 🎨 **Community art** uploads, described and categorised by the vision model; pieces that already carry Pepecoin branding are served without the watermark
- 🌙 **Dark & light themes** with smooth transitions
- ✨ **Polished animations** via Framer Motion
- 📝 **Markdown rendering** for assistant responses
- 🔗 **Clickable links** in responses
- 🌐 **Language detection** based on user input

## Project structure

```
zen-ai-agent/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── api/                 # routes and request schemas
│   ├── services/            # chat, images, community art, intent detection
│   ├── rag/                 # Qdrant store, chunking, retrieval
│   ├── knowledge/           # markdown the agent retrieves as context (versioned here)
│   ├── scripts/             # ingest_knowledge.py and other one-off tools
│   ├── data/                # persistent volume: SQLite, uploads, caches (git-ignored)
│   ├── requirements.txt
│   ├── assets/
│   │   └── watermark.png
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── components/
    │   ├── hooks/
    │   └── styles/
    ├── package.json
    ├── tailwind.config.js
    └── vite.config.js
```

## Required environment variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Your Google Gemini API key |
| `QDRANT_URL` | Qdrant cluster URL |
| `QDRANT_API_KEY` | Qdrant API key |
| `QDRANT_COLLECTION` | Name of the knowledge collection (default: `professor_pepe`) |

Optional:

| Variable | Description |
|----------|-------------|
| `IMAGE_API_BASE` | Image API base URL (default: `https://onlypepes.com`) |
| `MEMES_DIR` | Local directory for rare pepe image files |

## Local setup

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your keys:

```bash
cp .env.example .env
```

Run the server:

```bash
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and proxies API calls to the backend.

## Knowledge base

What the agent knows beyond the model lives in `backend/knowledge/*.md`, one
file per topic. Retrieval hands the model single chunks (about 500
characters, split at blank lines), so write each section to stand on its
own: a heading directly followed by its paragraph, no blank line between,
and say in the paragraph what it is about.

Ingest against the deployed server (that is where the Qdrant and Gemini
credentials are):

```bash
cd backend
ADMIN_TOKEN=... python scripts/ingest_knowledge.py            # every file
ADMIN_TOKEN=... python scripts/ingest_knowledge.py knowledge/one-file.md
```

Re-running after an edit replaces that file's chunks; nothing stale stays
retrievable. `API_BASE` overrides the target server.

## Admin endpoints

All take `Authorization: Bearer $ADMIN_TOKEN`.

| Endpoint | What it does |
|----------|--------------|
| `POST /api/ingest/file` | Ingest one text/markdown file (what the script above calls) |
| `POST /api/ingest/text` | Ingest a raw string |
| `GET/PUT/DELETE /api/admin/community-art[/{id}]` | Review uploads; `PUT` takes `status`, `label` and optionally `has_branding` |
| `POST /api/admin/community-art/relabel` | Name every piece from its picture (`?only_missing=true` for unnamed ones) |
| `POST /api/admin/community-art/detect-branding` | Decide for each piece whether it already carries Pepecoin branding, so it is served without the watermark. Run once after deploying; `?only_unknown=false` re-judges everything |

## Pictures and the watermark

Every picture the chat shows goes through `GET /api/watermark?url=…` or
`?path=…` and carries the Professor Pepe mark. The same route with
`&watermark=false` returns the untouched file; that is what the *Original*
download button requests. Both variants are cached on the volume.
Exceptions that are served as they are: video clips, and community art the
vision model (or an admin) marked as already branded.

## Custom domain

After deploying on Render, go to **Settings → Custom Domains** and add `gpt.pepe`. Render will show you the DNS records to add at your domain provider. Use your DNS key to create an **A record** (or CNAME) pointing to Render.

## License

MIT
