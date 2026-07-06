import shutil
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from parser import extract_text
from ollama_client import score_resume
from database import Base, engine, get_db
from models import User, ScreeningHistory
from schemas import SignupRequest, LoginRequest, TokenResponse
from auth import hash_password, verify_password, create_access_token, get_current_user

app = FastAPI()

# TODO once your Vercel domain is known, replace "*" with your exact
# Vercel URL (e.g. ["https://your-project.vercel.app"]) to lock this down.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Creates tables on startup if they don't exist yet.
# Fine for a portfolio project; a larger app would use Alembic migrations instead.
Base.metadata.create_all(bind=engine)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "resume-screener-backend"}


@app.post("/auth/signup", response_model=TokenResponse)
async def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(str(user.id), user.email)
    return {"access_token": token}


@app.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(str(user.id), user.email)
    return {"access_token": token}


@app.post("/screen")
async def screen_resumes(
    jd: str = Form(...),
    resumes: list[UploadFile] = File(...),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = []

    for resume_file in resumes:
        path = os.path.join(UPLOAD_DIR, resume_file.filename)
        try:
            with open(path, "wb") as f:
                shutil.copyfileobj(resume_file.file, f)

            text = extract_text(path)
            if not text or not text.strip():
                raise ValueError("No extractable text found in the file (empty or unsupported format)")

            evaluation = score_resume(jd, text)

            results.append({
                "filename": resume_file.filename,
                "score": int(evaluation.get("score", 0)),
                "matched_skills": evaluation.get("matched_skills", []),
                "missing_skills": evaluation.get("missing_skills", []),
                "summary": evaluation.get("summary", "No evaluation summary generated."),
                "verdict": evaluation.get("verdict", "Unknown Match"),
            })
        except Exception as e:
            results.append({
                "filename": resume_file.filename,
                "score": 0,
                "matched_skills": [],
                "missing_skills": [],
                "summary": f"Failed to process this resume: {e}",
                "verdict": "Error",
            })
        finally:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass

    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    history_entry = ScreeningHistory(
        user_id=uuid.UUID(user["id"]),
        job_description=jd,
        results=results,
    )
    db.add(history_entry)
    db.commit()

    return {"results": results}


@app.get("/history")
async def get_history(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(ScreeningHistory)
        .filter(ScreeningHistory.user_id == uuid.UUID(user["id"]))
        .order_by(ScreeningHistory.created_at.desc())
        .all()
    )
    return {
        "history": [
            {
                "id": str(r.id),
                "job_description": r.job_description,
                "results": r.results,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }
