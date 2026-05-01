# utils/ai_client.py
"""
Thin async wrapper around Gemini / OpenAI.
Set PROVIDER env var to 'gemini' (default) or 'openai'.
"""

import asyncio
import os

PROVIDER = os.getenv("PROVIDER", "gemini").lower()

# One global semaphore so we never flood the AI provider
_sem = asyncio.Semaphore(3)


async def analyze_text(prompt: str) -> str:
    async with _sem:
        if PROVIDER == "gemini":
            return await asyncio.to_thread(_call_gemini, prompt)
        if PROVIDER == "openai":
            return await asyncio.to_thread(_call_openai, prompt)
        return "⚠️ No AI provider configured. Set the PROVIDER env var."


# ── Gemini ────────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    try:
        import google.genai as genai
    except ImportError:
        return "⚠️ google-genai not installed. Run: pip install google-genai"

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ GEMINI_API_KEY is not set."

    model = os.getenv("GEMINI_MODEL", "models/gemma-4-26b-a4b-it")
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )
        # Prefer .text shortcut, fall back to candidates
        if getattr(response, "text", None):
            return response.text.strip()
        candidates = getattr(response, "candidates", None)
        if candidates:
            content = getattr(candidates[0], "content", None)
            if content:
                part = content[0] if isinstance(content, list) else content
                return (getattr(part, "text", None) or str(part)).strip()
        return str(response)
    except Exception as exc:
        return f"⚠️ Gemini error: {exc}"


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _call_openai(prompt: str) -> str:
    """Uses the openai ≥ 1.0 client (ChatCompletion was removed in v1)."""
    try:
        from openai import OpenAI
    except ImportError:
        return "⚠️ openai not installed. Run: pip install openai"

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "⚠️ OPENAI_API_KEY is not set."

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.6,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"⚠️ OpenAI error: {exc}"
