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


load_dotenv()


YOUR_SECRET = os.getenv('YOUR_SECRET')
YOUR_EMAIL = os.getenv('YOUR_EMAIL')


if not YOUR_SECRET or not YOUR_EMAIL:
    print("Warning: Set YOUR_SECRET and YOUR_EMAIL in your environment (.env)")


app = FastAPI()


class QuizPayload(BaseModel):
    email: str
    secret: str
    url: str


@app.post('/quiz')
def receive_quiz(payload: QuizPayload):
# Validate JSON -- pydantic raises 422 if malformed
    if payload.secret != YOUR_SECRET:
        raise HTTPException(status_code=403, detail='Invalid secret')


    start = time.time()
    solver = QuizSolver(email=payload.email, secret=payload.secret)


    try:
        result = solver.solve_and_submit(payload.url, time_budget_sec=170)
    except Exception as e:
        # ensure we return 200 as long as secret matched; include error info for debugging
        return {"status":"error","error":str(e)}


    elapsed = time.time() - start
    return {"status":"ok","elapsed_sec": elapsed, "result": result}