from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    host = os.getenv("VERA_HOST", "127.0.0.1")
    port = int(os.getenv("VERA_PORT", "8080"))
    uvicorn.run("api_server:app", host=host, port=port, reload=False)
