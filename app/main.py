from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import scenarios, chat, sessions

app = FastAPI(
    title="Nurse LLM",
    description="AI-powered nursing assessment chatbot for student education",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Streamlit needs to call the API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])


@app.get("/")
async def root():
    return {"status": "ok", "message": "Nurse LLM API is running"}
