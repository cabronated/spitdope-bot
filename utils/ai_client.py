# utils/ai_client.py
"""
Thin async wrapper around Gemini / OpenAI.
Set PROVIDER env var to 'gemini' (default) or 'openai'.
"""

import asyncio
import os

PROVIDER = os.getenv("PROVIDER", "gemini").lower()

_sem = asyncio.Semaphore(3)


async def analyze_text(prompt: str) -> str:
    async with _sem:
        if PROVIDER == "gemini":
            return await asyncio.to_thread(_call_gemini, prompt)
        if PROVIDER == "openai":
            return await asyncio.to_thread(_call_openai, prompt)
        raise RuntimeError("No AI provider configured. Set the PROVIDER env var.")


# ── Gemini ────────────────────────────────────────────────────────────────────

def _call_gemini(prompt: str) -> str:
    try:
        import google.genai as genai
    except ImportError:
        raise RuntimeError("google-genai not installed. Run: pip install google-genai")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    model = os.getenv("GEMINI_MODEL", "models/gemma-4-26b-a4b-it")

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
            text = getattr(part, "text", None)
            if text:
                return text.strip()

    raise RuntimeError(f"Gemini returned an unreadable response: {response!r}")


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _call_openai(prompt: str) -> str:
    """Uses the openai ≥ 1.0 client (ChatCompletion was removed in v1)."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.6,
    )
    return resp.choices[0].message.content.strip()
