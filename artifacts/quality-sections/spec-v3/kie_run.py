#!/usr/bin/env python
"""Run a spec-v3 prompt on kie.ai (GPT Image 2.5 Sunburst), the same job sent to
Higgsfield, so the two services can be compared.

Usage: kie_run.py <prompt file> <out prefix> [count] [kie model id]
The reference images are the copies already uploaded to Higgsfield (public URLs).
"""
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "photo-mockup-spike"))
import kie_client  # noqa: E402

CDN = "https://d2ol7oe51mr4n9.cloudfront.net/user_3B5TkezxpmVdHyrxuPfJm8d9U8w/"
REFS = [CDN + f for f in (
    "e6f88d33-6021-4fe0-8f9f-8177ac6cf81b.png",  # 1 studio setting (Evan's reference)
    "ff0bbe35-472a-440f-8b28-aa6ef1ec8625.jpg",  # 2 bomber, forest green
    "fb6c3bfa-853c-440b-9073-00592f674094.jpg",  # 3 hoodie, navy
    "4e3858c5-7003-4df4-8160-894d7f8cd830.jpg",  # 4 sweatshirt, black
    "18c3f177-4954-4929-a150-21e9fbab3e78.jpg",  # 5 tee, maroon
)]


def one(i, prompt, prefix, model):
    r = kie_client.create(prompt, REFS, resolution="4K", aspect_ratio="3:2", model=model)
    task = (r.get("data") or {}).get("taskId")
    if not task:
        raise RuntimeError(f"create failed: {r}")
    data = kie_client.wait(task, timeout=900)
    urls = kie_client.result_urls(data)
    out = HERE / "render" / f"{prefix}-{chr(97 + i)}.png"
    urllib.request.urlretrieve(urls[0], out)
    return f"{out.name}  task {task}"


if __name__ == "__main__":
    prompt = (HERE / sys.argv[1]).read_text()
    prefix, n = sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 3
    model = sys.argv[4] if len(sys.argv) > 4 else kie_client.MODEL
    with ThreadPoolExecutor(n) as ex:
        for line in ex.map(lambda i: one(i, prompt, prefix, model), range(n)):
            print(line)
