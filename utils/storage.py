# utils/storage.py
import os
import json
import aiofiles
from typing import Any

DATA_DIR = "bot_data"
os.makedirs(DATA_DIR, exist_ok=True)

async def load_json(path: str, default: Any):
    if not os.path.exists(path):
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(default, indent=2))
        return default
    async with aiofiles.open(path, "r") as f:
        txt = await f.read()
    return json.loads(txt) if txt else default

async def save_json(path: str, data: Any):
    async with aiofiles.open(path, "w") as f:
        await f.write(json.dumps(data, indent=2))

def guild_file(guild_id: int) -> str:
    return os.path.join(DATA_DIR, f"{guild_id}.json")