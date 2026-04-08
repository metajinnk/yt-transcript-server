from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.options("/transcript")
async def options_transcript():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )

class TranscriptRequest(BaseModel):
    url: str

def get_video_id(url: str) -> str:
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("유효한 YouTube URL이 아닙니다.")

@app.get("/")
def root():
    return {"status": "ok", "message": "YouTube Transcript Server"}

@app.post("/transcript")
def get_transcript(req: TranscriptRequest):
    try:
        video_id = get_video_id(req.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ytt = YouTubeTranscriptApi()

    try:
        transcript = ytt.fetch(video_id, languages=["ko", "en"])
    except Exception:
        try:
            transcript_list = ytt.list(video_id)
            first = next(iter(transcript_list))
            transcript = first.fetch()
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"자막을 찾을 수 없습니다: {str(e)}")

    full_text = " ".join([t.text for t in transcript])

    return {
        "video_id": video_id,
        "url": req.url,
        "transcript": full_text,
        "char_count": len(full_text)
    }
