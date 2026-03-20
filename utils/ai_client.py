# utils/ai_client.py
import os
import asyncio

PROVIDER = os.getenv("PROVIDER", "gemini").lower()
_api_lock = asyncio.Lock()

async def analyze_text(prompt: str) -> str:
    async with _api_lock:
        await asyncio.sleep(0.2)
        if PROVIDER == "gemini":
            return await _call_gemini(prompt)
        elif PROVIDER == "openai":
            return await _call_openai(prompt)
        return "⚠️ No provider configured."

# -------------------------
# Gemini 3.1 Flash Lite — MINIMAL SIGNATURE VERSION
# -------------------------
async def _call_gemini(prompt: str) -> str:
    try:
        import google.genai as genai
    except Exception as e:
        return f"⚠️ google.genai not installed: {e}"

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ GEMINI_API_KEY missing."

    model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.5-flash-lite")

    def sync_call():
        try:
            client = genai.Client(api_key=api_key)

            # STRICT MINIMAL CALL — your SDK only accepts these two arguments
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            )

            # Extract text (Gemini 3.x)
            if hasattr(response, "text") and response.text:
                return response.text.strip()

            # Candidates format
            if hasattr(response, "candidates") and response.candidates:
                c = response.candidates[0]

                if hasattr(c, "content") and c.content:
                    part = c.content[0]
                    if hasattr(part, "text"):
                        return part.text.strip()
                    if hasattr(part, "value"):
                        return str(part.value).strip()

                if hasattr(c, "text"):
                    return c.text.strip()

            return str(response)

        except Exception as e:
            return f"⚠️ Gemini error: {e}"

    return await asyncio.to_thread(sync_call)

# -------------------------
# OpenAI fallback
# -------------------------
async def _call_openai(prompt: str) -> str:
    try:
        import openai
        openai.api_key = os.getenv("OPENAI_API_KEY")

        def sync_call():
            resp = openai.ChatCompletion.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.6
            )
            return resp["choices"][0]["message"]["content"].strip()

        return await asyncio.to_thread(sync_call)

    except Exception as e:
        return f"⚠️ OpenAI error: {e}"
