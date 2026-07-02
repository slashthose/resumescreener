import httpx
import json
import os

# Grab the API key from environment variables (configured in Render/Railway)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama3.1-8b-instant"  # Fast, highly accurate open-source Llama 3 model

def score_resume(jd: str, resume: str) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY environment variable is missing!")

    prompt = f"""You are an expert HR recruiter. Given the job description and resume below,
evaluate how well the candidate matches the role.

Respond ONLY with valid JSON in this exact format (no extra text):
{{
  "score": <0-100>,
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1", "skill2"],
  "summary": "<2-sentence evaluation>",
  "verdict": "<Strong Match | Moderate Match | Weak Match>"
}}

JOB DESCRIPTION:
{jd}

RESUME:
{resume[:3000]}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}, # Forces the model to return valid JSON
        "temperature": 0.2
    }

    try:
        response = httpx.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Groq API error: {e.response.status_code} {e.response.text[:200]}")

    # Parse the standard OpenAI/Groq response format
    result_data = response.json()
    raw = result_data["choices"][0]["message"]["content"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse model JSON output: {e}. Raw snippet: {raw[:200]}")
