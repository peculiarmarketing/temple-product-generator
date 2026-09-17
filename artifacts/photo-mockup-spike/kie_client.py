#!/usr/bin/env python
"""Minimal kie.ai client for GPT Image 2.5 (Sunburst).

Why this exists: generating each colourway by referencing the previous
generation stacked 3-4 passes deep and the subject drifted - hair went from
photographic to rendered. See genloss_hair.jpg. Every image should instead be
ONE generation from the original Tapstitch reference photo.

kie.ai takes reference images as URLs, and Tapstitch's catalogue images are
already public URLs, so nothing needs uploading.

The API key is never read into this file. It comes from KIE_API_KEY in the
environment or in a .env, and only the header ever sees it.
"""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

BASE = "https://api.kie.ai/api/v1"
MODEL = "gpt-image-2-5-sunburst-image-to-image"


def _load_key():
    if os.environ.get("KIE_API_KEY"):
        return os.environ["KIE_API_KEY"]
    here = Path(__file__).resolve()
    repo = here.parent.parent.parent
    for env in (repo / ".env", repo.parent.parent / ".env", repo.parent / ".env"):
        if not env.exists():
            continue
        for line in env.read_text().splitlines():
            m = re.match(r"^\s*KIE_API_KEY\s*=\s*(.*)$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("KIE_API_KEY not found in environment or any .env")


def _call(method, path, body=None):
    req = urllib.request.Request(
        f"{BASE}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {_load_key()}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def credit():
    return _call("GET", "/chat/credit")


def create(prompt, input_urls, resolution="2K", aspect_ratio="1:1", model=MODEL):
    payload = {"model": model,
               "input": {"prompt": prompt, "input_urls": input_urls,
                         "resolution": resolution, "aspect_ratio": aspect_ratio}}
    return _call("POST", "/jobs/createTask", payload)


def wait(task_id, timeout=600, every=6):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = _call("GET", f"/jobs/recordInfo?taskId={task_id}")
        d = r.get("data") or {}
        state = d.get("state") or d.get("status")
        if state != last:
            print(f"  {task_id[:8]} -> {state}")
            last = state
        if state in ("success", "completed", "SUCCESS"):
            return d
        if state in ("fail", "failed", "FAIL", "error"):
            raise RuntimeError(json.dumps(d)[:500])
        time.sleep(every)
    raise TimeoutError(task_id)


def result_urls(data):
    """Pull image URLs out of whatever shape the result comes back in."""
    for key in ("resultUrls", "resultJson", "result", "output"):
        v = data.get(key)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                if v.startswith("http"):
                    return [v]
                continue
        if isinstance(v, dict):
            for k in ("resultUrls", "urls", "images", "image_urls"):
                if v.get(k):
                    return v[k]
        if isinstance(v, list) and v:
            return v
    return []


if __name__ == "__main__":
    print(json.dumps(credit(), indent=1))
