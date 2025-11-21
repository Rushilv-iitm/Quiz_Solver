import os
import time
import json
import tempfile
import base64
import re
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from solver import QuizSolver
from fastapi.responses import HTMLResponse, FileResponse

# -------------------------
# MAIN FASTAPI INSTANCE
# -------------------------
app = FastAPI()

# Root route (homepage)
@app.get("/", response_class=HTMLResponse)
async def root():
    return "<html><head><title>Quiz Solver</title></head><body><h1>Quiz Solver is live 🎉</h1></body></html>"

# Favicon route
@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")

# Load environment variables
load_dotenv()
YOUR_SECRET = os.getenv('YOUR_SECRET')
YOUR_EMAIL = os.getenv('YOUR_EMAIL')

if not YOUR_SECRET or not YOUR_EMAIL:
    print("Warning: Set YOUR_SECRET and YOUR_EMAIL in your environment (.env)")

# -------------------------
# QUIZ SOLVER ENDPOINT
# -------------------------
class QuizPayload(BaseModel):
    email: str
    secret: str
    url: str

@app.post('/quiz')
def receive_quiz(payload: QuizPayload):

    # Secret validation
    if payload.secret != YOUR_SECRET:
        raise HTTPException(status_code=403, detail='Invalid secret')

    start = time.time()
    solver = QuizSolver(email=payload.email, secret=payload.secret)

    try:
        result = solver.solve_and_submit(payload.url, time_budget_sec=170)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    elapsed = time.time() - start

    return {"status": "ok", "elapsed_sec": elapsed, "result": result}
