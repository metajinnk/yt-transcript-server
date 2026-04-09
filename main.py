from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = FastAPI()

def cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Accept",
    }

@app.middleware("http")
async def add_cors(request: Request, call_next):
    if request.method == "OPTIONS":
        return JSONResponse(content={}, headers=cors_headers())
    response = await call_next(request)
    for k, v in cors_headers().items():
        response.headers[k] = v
    return response

class TranscriptRequest(BaseModel):
    url: str

def get_video_id(url: str) -> str:
    for pattern in [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    raise ValueError("유효한 YouTube URL이 아닙니다.")

@app.get("/")
def root():
    return JSONResponse({"status": "ok"}, headers=cors_headers())

@app.post("/transcript")
def get_transcript(req: TranscriptRequest):
    try:
        video_id = get_video_id(req.url)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400, headers=cors_headers())

    ytt = YouTubeTranscriptApi()
    try:
        transcript = ytt.fetch(video_id, languages=["ko", "en"])
    except Exception:
        try:
            first = next(iter(ytt.list(video_id)))
            transcript = first.fetch()
        except Exception as e:
            return JSONResponse({"detail": f"자막을 찾을 수 없습니다: {e}"}, status_code=404, headers=cors_headers())

    full_text = " ".join([t.text for t in transcript])
    return JSONResponse({
        "video_id": video_id,
        "url": req.url,
        "transcript": full_text,
        "char_count": len(full_text)
    }, headers=cors_headers())
