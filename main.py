from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import re
import subprocess
import json
import tempfile
import os

app = FastAPI()

def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp

@app.middleware("http")
async def add_cors(request: Request, call_next):
    if request.method == "OPTIONS":
        r = JSONResponse({})
        return cors(r)
    response = await call_next(request)
    cors(response)
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
    return JSONResponse({"status": "ok", "message": "YouTube Transcript Server (yt-dlp)"})

@app.post("/transcript")
def get_transcript(req: TranscriptRequest):
    try:
        video_id = get_video_id(req.url)
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", "ko,en",
            "--sub-format", "json3",
            "--skip-download",
            "--no-warnings",
            "-o", out_path,
            f"https://www.youtube.com/watch?v={video_id}"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # 자막 파일 찾기
        sub_file = None
        for fname in os.listdir(tmpdir):
            if fname.endswith(".json3"):
                sub_file = os.path.join(tmpdir, fname)
                break

        if not sub_file:
            # vtt 시도
            cmd2 = [
                "yt-dlp",
                "--write-auto-sub",
                "--write-sub",
                "--sub-lang", "ko,en",
                "--sub-format", "vtt",
                "--skip-download",
                "--no-warnings",
                "-o", out_path,
                f"https://www.youtube.com/watch?v={video_id}"
            ]
            subprocess.run(cmd2, capture_output=True, text=True, timeout=60)
            for fname in os.listdir(tmpdir):
                if fname.endswith(".vtt"):
                    sub_file = os.path.join(tmpdir, fname)
                    break

        if not sub_file:
            return JSONResponse({
                "detail": f"자막을 찾을 수 없습니다. stderr: {result.stderr[:500]}"
            }, status_code=404)

        with open(sub_file, "r", encoding="utf-8") as f:
            content = f.read()

        # VTT 파싱
        if sub_file.endswith(".vtt"):
            lines = content.split("\n")
            texts = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith("WEBVTT") or "-->" in line or line.startswith("NOTE"):
                    continue
                # 중복 제거
                if texts and texts[-1] == line:
                    continue
                texts.append(line)
            full_text = " ".join(texts)
        else:
            # json3 파싱
            try:
                data = json.loads(content)
                texts = [e.get("segs", [{}])[0].get("utf8", "") for e in data.get("events", []) if e.get("segs")]
                full_text = " ".join(t for t in texts if t.strip() and t != "\n")
            except Exception:
                full_text = content

        return JSONResponse({
            "video_id": video_id,
            "url": req.url,
            "transcript": full_text.strip(),
            "char_count": len(full_text.strip())
        })
