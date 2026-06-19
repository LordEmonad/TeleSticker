# Test Coverage Analysis & Improvement Proposal

_Date: 2026-06-19_

## Summary

The codebase currently has **no automated tests at all** — there is no `tests/`
directory, no `pytest`/`unittest` suites, no test framework in
`requirements.txt`, and no CI configuration. Every module (≈1,650 lines of
Python across services, routes, models, and utils) is untested.

This document inventories what exists, ranks where tests would deliver the most
value, and proposes a concrete starting point.

## Current state

| Area | Files | Lines | Tests |
|------|-------|-------|-------|
| Routes (HTTP API) | 7 | ~440 | 0 |
| Services (processing/IO) | 8 | ~720 | 0 |
| Models (dataclasses) | 3 | ~105 | 0 |
| Utils / config | 2 | ~110 | 0 |
| **Total** | **20** | **~1,655** | **0** |

There is also no test tooling installed (`pytest` is absent) and dependencies
are not pinned for a test environment.

## Recommended priorities

### 1. Pure logic in `app/utils.py` and the models — _highest ROI, lowest effort_

These functions are deterministic, dependency-light, and underpin upload
validation. They are the easiest to test and the cheapest to keep green.

- `detect_file_type()` — extension → `image` / `video` / `animated_gif` / `None`.
- `validate_file()` — accept/reject + size warnings.
- `format_size()` — byte formatting across B/KB/MB/GB/TB boundaries.
- `Job.progress` / `Job.to_dict()` — progress math, including the
  `total_files == 0` divide-by-zero guard.
- `Sticker.to_dict()` / `Pack.to_dict()` — serialization shape (the API
  contract the frontend depends on).

**Bug this would catch immediately:** `detect_file_type()` returns
`'animated_gif'` for **every** `.gif`, because `ANIMATED_EXTENSIONS = {'gif'}`
is checked before `IMAGE_EXTENSIONS`. As a result, the correction branch in
`upload.py`
(`if file_type == 'image' and filename.lower().endswith('.gif') and is_animated_gif(...)`)
is **dead code** — a static, single-frame GIF is always classified as animated
and pushed through the video/WEBM pipeline. A unit test pinning the intended
behavior would surface this.

### 2. HTTP route contracts via Flask test client — _high value_

Use `app.test_client()` with services mocked. These cover the request/response
contract, status codes, and validation branches without touching FFmpeg, rembg,
or the network.

- **Upload** (`/api/upload`, `/api/process`): rejects empty/invalid files
  (400), filenames are run through `secure_filename`, `/api/process` with no
  valid `file_id` returns 400, unknown `job_id` returns 404.
- **Pack CRUD** (`/api/pack`): missing `name`/`title` → 400, create → 201,
  get/update/delete of a missing pack → 404. `pack_manager` is a clean
  JSON-persistence layer that can be tested against a `tmp_path` packs folder.
- **Telegram** (`/api/telegram/*`): missing fields → 400, no valid stickers →
  400, missing token → 400/401 — all with `telegram_api` mocked so no real
  Bot API call is made.
- **Editor** (`/api/editor/*`): `bg-status` reflects availability, and
  `remove-bg` returns **503** when rembg is unavailable, **404** for unknown
  `file_id`, **400** for non-image types.
- **Preview/download path safety** (see #4).

### 3. Image processing with Pillow — _testable without external binaries_

`image_processor.py` only needs Pillow (already a dependency), so these run in
CI without FFmpeg:

- `resize_image()` — longest side becomes 512 for stickers, exact 100×100 for
  icon/emoji, even dimensions, and the **iterative WEBP quality reduction** that
  enforces the size cap (generate a large image, assert output ≤ limit).
- `detect_transparency()` — RGBA-with-alpha vs opaque RGB vs palette
  transparency.
- `generate_thumbnail()` — RGBA → PNG, otherwise WEBP; returns `False` on a
  corrupt file instead of raising.

### 4. Security regression tests — _explicitly worth pinning_

The last substantive commit was _"Fix security vulnerabilities and broken
processing pipeline."_ Security fixes without regression tests tend to silently
regress. Pin them:

- **Path traversal** in `/api/preview/<filename>` and `/api/download/<filename>`
  — assert a `../../etc/passwd`-style request cannot escape `UPLOAD_FOLDER` /
  `OUTPUT_FOLDER`. Note `download.py` passes the raw filename to
  `send_from_directory` **without** `secure_filename`, unlike `preview.py` —
  worth a test to confirm Werkzeug's own guard holds and to document the
  asymmetry.
- **CORS allow-list** on the Socket.IO server (`extensions.py`) stays
  restricted to localhost origins.
- **Secret key** falls back to a random value when `TELESTICKER_SECRET_KEY` is
  unset (config behavior).

### 5. Job queue orchestration — _mock the converters_

`job_queue.submit_job()` is the heart of the pipeline. Test the orchestration
logic with `resize_image` / `convert_video` / `convert_gif_to_video` mocked and
a fake `socketio`:

- Routing by `file_type` (image → `resize_image`, video/animated → video path).
- Cancellation: setting `job.cancelled` stops further processing and emits a
  `cancelled` status.
- Per-file failure is isolated (one bad file doesn't abort the batch) and emits
  a `file_processed` error event.
- ZIP is produced only when there are results; an all-failures job ends in
  `error` status.
- `sticker_store` is updated with `processed_path` / `status` on success.

> Note: `submit_job` uses a module-level `ThreadPoolExecutor` and an in-memory
> `_jobs` dict. For deterministic tests, refactor slightly to allow running the
> `process()` body synchronously (e.g. an injectable executor), or assert via
> the emitted events after a join.

### 6. External-boundary code — _mock, don't call_

- `telegram_api.py` — wrap `httpx` (already lazily injected via `_get_httpx`,
  which makes mocking easy) and assert the `createNewStickerSet` /
  `addStickerToSet` payload shape, the `ok: False` error handling, and the
  multi-sticker loop that collects per-sticker errors.
- `video_processor.py` — mock `subprocess.run` to assert the FFmpeg command is
  built correctly (even dimensions, `-t 3` duration cap, the bitrate
  back-off loop, `.webm` extension coercion) and that timeouts return `False`.
- `background_remover.py` — `is_available()` caching, and the
  retry-without-alpha-matting fallback on failure (rembg mocked).

## Suggested tooling & layout

```
requirements-dev.txt   # pytest, pytest-cov, pytest-mock
pytest.ini             # testpaths=tests, coverage config
conftest.py            # app fixture, Flask test client, tmp upload/output/packs dirs
tests/
  unit/
    test_utils.py
    test_models.py
    test_image_processor.py
    test_pack_manager.py
  routes/
    test_upload_routes.py
    test_pack_routes.py
    test_telegram_routes.py
    test_editor_routes.py
    test_preview_security.py
  services/
    test_job_queue.py
    test_telegram_api.py
    test_video_processor.py
```

Key fixtures: a `tmp_path`-backed config override for
`UPLOAD_FOLDER`/`OUTPUT_FOLDER`/`PACKS_FOLDER` (so tests never touch real
project dirs), a Flask app/test-client fixture, and a small helper that
generates in-memory Pillow images.

## Suggested first milestone

A high-signal, fast, dependency-light starter suite:

1. `test_utils.py` + `test_models.py` (pure logic — and surfaces the GIF
   classification bug).
2. `test_pack_manager.py` + `test_pack_routes.py` (clean CRUD, easy to mock).
3. `test_preview_security.py` (locks in the path-traversal fix).

This establishes the framework, fixtures, and CI hook, and can realistically
reach meaningful coverage of the deterministic core before tackling the
FFmpeg/rembg/Telegram boundaries with mocks.
