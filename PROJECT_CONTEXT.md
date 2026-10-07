#  Project Context

Demo AI agent that promotes tzelahahar.co.il (vacation cabins and villas in
Northern Israel). Every day it produces 3 posts and 3 stories in Hebrew
and English, then runs them through review, approval, scheduling and publishing.

## Stack
Backend: Python 3.11/3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL (Neon or
local), ChromaDB, OpenAI (writing, translation, embeddings), Groq (planning,
review), LangGraph, APScheduler, Pillow + python-bidi, httpx, BeautifulSoup,
Playwright.
Frontend: React + Vite + Tailwind v4, React Router, Axios, lucide-react, RTL-first.

## Environment rules
- OS is Windows + PowerShell. Docker is NOT available. Never create Docker files.
- Backend runs from /backend with: uvicorn app.main:app --reload --port 8000
- Venv is /backend/.venv. Config via /backend/.env (never hardcode or log keys).
- Timezone: Asia/Jerusalem (requires the tzdata package).
- Models must work on PostgreSQL and SQLite (JSON with a JSONB variant on Postgres).
- Playwright: use the sync API inside normal def endpoints or threads, never the
  async API (breaks under uvicorn on Windows).

## Hard rules
- Real social APIs (Facebook, Instagram, TikTok, X) do NOT exist in this demo.
  Only mock publishers. Never claim a mock publish went to a real platform.
  Telegram may be real if credentials exist.
- Never invent prices, amenities, availability, discounts or addresses.
  Content uses only data scraped from the website.
- Everything outside /adapters depends only on BasePublisher.
- Israel weekend is Friday/Saturday.

## Architecture
Website -> ingestion -> Postgres + Chroma -> LangGraph
(planner[Groq] -> writer[OpenAI] -> creative[Pillow] -> reviewer[Groq] -> router)
-> approval workflow -> APScheduler -> publisher adapters -> feeds/logs
-> React dashboard.

## Status flow
draft -> pending_approval -> approved -> scheduled -> published | failed | rejected

## Working method
One phase at a time. After each phase: list files created, commands to run,
and how to test. Do not build features from later phases.