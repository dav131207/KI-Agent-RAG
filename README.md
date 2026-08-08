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

- 💬 **Chat** with streaming responses
- 🖼️ **Random Meme / Rare Pepe / Social Media Post** commands
- 🌙 **Dark & light themes** with smooth transitions
- ✨ **Polished animations** via Framer Motion
- 📝 **Markdown rendering** for assistant responses
- 🔗 **Clickable links** in responses
- 🌐 **Language detection** based on user input

## Project structure

```
zen-ai-agent/
├── backend/
│   ├── main.py              # FastAPI + Gemini + image proxy
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

## Custom domain

After deploying on Render, go to **Settings → Custom Domains** and add `gpt.pepe`. Render will show you the DNS records to add at your domain provider. Use your DNS key to create an **A record** (or CNAME) pointing to Render.

## License

MIT
