import logging
import os

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from summarizerlib.summary import SummaryGenerator

LLAMA_SERVER_HOST = os.getenv('LLAMA_SERVER_HOST', 'localhost')
LLAMA_SERVER_PORT = os.getenv('LLAMA_SERVER_PORT', 8080)
LLAMA_SERVER_ENDPOINT = f'http://{LLAMA_SERVER_HOST}:{LLAMA_SERVER_PORT}/completion'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI()
generator = SummaryGenerator(LLAMA_SERVER_ENDPOINT)


@app.get('/summarize-url')
async def summarize_url(url: str = Query(..., description='Slack message permalink')):
    result = await generator.summarize_thread_by_permalink(url)
    return JSONResponse(content={'summary': result})


@app.get('/summarize-art-attention')
async def summarize_art_attention():
    summaries = await generator.summarize_art_attention_threads()
    return JSONResponse(content={'summaries': summaries})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # optional: enables auto-reload on code changes
        log_level="info"
    )
