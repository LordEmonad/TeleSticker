"""The HTTP side: the page, the API, SSE. Flask, threaded; nothing else."""
import io
import logging
import mimetypes
import os
import shutil
import tempfile
import threading
import time
import zipfile

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

from . import events, export, library, publish, render, telegram
from .config import ALL_EXT, APP_NAME, MAX_UPLOAD_BYTES, TARGETS, TG, VERSION, WEB_DIR, ensure_dirs, ffmpeg_bin
from .media import rembg_bridge

log = logging.getLogger('emosticker')
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('video/webm', '.webm')


def create_app():
    ensure_dirs()
    app = Flask(APP_NAME, static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES

    @app.after_request
    def headers(resp):
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['Referrer-Policy'] = 'no-referrer'
        resp.headers['Cache-Control'] = resp.headers.get('Cache-Control', 'no-store')
        return resp

    @app.before_request
    def same_origin_writes():
        # a page on another site cannot drive this local app: writes must come from our own origin
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            origin = request.headers.get('Origin') or ''
            if origin and origin.rstrip('/') != request.host_url.rstrip('/'):
                abort(403)

    # ---- the page -------------------------------------------------------------------------------------
    @app.get('/')
    def index():
        return send_from_directory(WEB_DIR, 'index.html')

    @app.get('/web/<path:path>')
    def web(path):
        resp = send_from_directory(WEB_DIR, path)
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    # ---- state ----------------------------------------------------------------------------------------
    @app.get('/api/state')
    def state():
        db = library.snapshot()
        st = library.settings()
        return jsonify(dict(
            version=VERSION, stickers=db['stickers'], packs=db['packs'], current_pack=db['current_pack'],
            targets={k: dict(label=v['label']) for k, v in TARGETS.items()}, tg=TG,
            tools=dict(ffmpeg=_have(ffmpeg_bin('ffmpeg')), ffprobe=_have(ffmpeg_bin('ffprobe')),
                       rembg=rembg_bridge.available(), rembg_models=rembg_bridge.MODELS),
            bot=dict(username=st.get('bot_username'), name=st.get('bot_name'), user_id=st.get('user_id'),
                     user_name=st.get('user_name'), has_token=bool(st.get('token'))),
            busy=events.busy(),
        ))

    @app.get('/api/events')
    def sse():
        q = events.subscribe()

        def gen():
            try:
                yield from events.stream(q)
            finally:
                events.unsubscribe(q)
        return Response(gen(), mimetype='text/event-stream',
                        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    # ---- intake ---------------------------------------------------------------------------------------
    @app.post('/api/upload')
    def upload():
        got = []
        for key in request.files:
            for f in request.files.getlist(key):
                if not f.filename:
                    continue
                name = secure_filename(f.filename) or 'file'
                ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
                if ext not in ALL_EXT:
                    got.append(dict(name=f.filename, error='not a picture or video we know'))
                    continue
                fd, tmp = tempfile.mkstemp(suffix='.' + ext, prefix='emosticker-in-')
                os.close(fd)
                f.save(tmp)
                try:
                    rec = render.intake(tmp, f.filename)
                    got.append(dict(name=f.filename, id=rec['id']))
                except Exception as e:
                    log.exception('intake failed')
                    got.append(dict(name=f.filename, error=str(e)[-200:]))
                    if os.path.exists(tmp):
                        os.remove(tmp)
        return jsonify(dict(files=got))

    @app.post('/api/fetch')
    def fetch_url():
        """A pasted link: download it here (this is a local app; nothing is proxied for anyone else)."""
        import httpx
        url = (request.json or {}).get('url', '').strip()
        if not url.startswith(('http://', 'https://')):
            return jsonify(error='Not a link'), 400
        try:
            with httpx.Client(follow_redirects=True, timeout=60) as c:
                r = c.get(url)
                r.raise_for_status()
                ctype = r.headers.get('content-type', '').split(';')[0]
                ext = mimetypes.guess_extension(ctype) or os.path.splitext(url.split('?')[0])[1] or '.bin'
                ext = ext.lstrip('.').lower()
                if ext == 'jpe':
                    ext = 'jpg'
                if ext not in ALL_EXT:
                    return jsonify(error=f'That link is {ctype or "not a picture or video"}'), 400
                fd, tmp = tempfile.mkstemp(suffix='.' + ext, prefix='emosticker-in-')
                os.write(fd, r.content)
                os.close(fd)
            name = os.path.basename(url.split('?')[0]) or f'download.{ext}'
            if '.' not in name:
                name += '.' + ext
            rec = render.intake(tmp, name)
            return jsonify(id=rec['id'])
        except Exception as e:
            return jsonify(error=str(e)[-200:]), 400

    # ---- stickers -------------------------------------------------------------------------------------
    @app.get('/api/sticker/<sid>')
    def get_sticker(sid):
        s = library.get_sticker(sid)
        return jsonify(s) if s else (jsonify(error='not found'), 404)

    @app.patch('/api/sticker/<sid>')
    def patch_sticker(sid):
        body = request.json or {}
        allowed = {k: v for k, v in body.items() if k in ('name', 'emoji', 'keywords', 'edit')}
        if 'edit' in allowed and body.get('replace_edit'):
            s = library.update_sticker(sid)
            if s:
                s['edit'] = allowed['edit']
                library.update_sticker(sid, edit_full=True)
        if 'emoji' in allowed:
            allowed['emoji'] = [e for e in allowed['emoji'] if isinstance(e, str) and e.strip()][: TG['emoji_per_sticker']] or ['🥀']
        if 'keywords' in allowed:
            kws, total = [], 0
            for k in allowed['keywords']:
                k = str(k).strip()[:64]
                if k and total + len(k) <= TG['keywords_total'] and len(kws) < 20:
                    kws.append(k); total += len(k)
            allowed['keywords'] = kws
        s = library.get_sticker(sid)
        if not s:
            return jsonify(error='not found'), 404
        if 'edit' in allowed:
            new_edit = dict(s.get('edit') or {})
            for k, v in allowed['edit'].items():
                if v is None:
                    new_edit.pop(k, None)
                else:
                    new_edit[k] = v
            s['edit'] = new_edit
            with library._lock:
                db = library._load()
                db['stickers'][sid]['edit'] = new_edit
                for k in ('name', 'emoji', 'keywords'):
                    if k in allowed:
                        db['stickers'][sid][k] = allowed[k]
                db['stickers'][sid]['updated'] = library.now()
                library._save()
            render.schedule_render(sid, final=not body.get('quick'))
        else:
            library.update_sticker(sid, **allowed)
        s = library.get_sticker(sid)
        events.emit('sticker', {'id': sid, 'record': s})
        return jsonify(s)

    @app.post('/api/sticker/<sid>/render')
    def rerender(sid):
        render.schedule_render(sid, final=True)
        return jsonify(ok=True)

    @app.delete('/api/sticker/<sid>')
    def delete_sticker(sid):
        ok = library.delete_sticker(sid)
        events.emit('removed', {'id': sid})
        return jsonify(ok=ok)

    @app.post('/api/sticker/<sid>/duplicate')
    def duplicate(sid):
        s = library.get_sticker(sid)
        if not s:
            return jsonify(error='not found'), 404
        src = s['source']['path']
        fd, tmp = tempfile.mkstemp(suffix=os.path.splitext(src)[1]); os.close(fd)
        shutil.copy(src, tmp)
        rec = render.intake(tmp, s['name'])
        library.update_sticker(rec['id'], edit=dict(s.get('edit') or {}), emoji=list(s.get('emoji') or []),
                               keywords=list(s.get('keywords') or []))
        render.schedule_render(rec['id'])
        return jsonify(library.get_sticker(rec['id']))

    @app.post('/api/sticker/<sid>/pick')
    def pick(sid):
        b = request.json or {}
        return jsonify(color=render.preview_pick(sid, float(b.get('x', .5)), float(b.get('y', .5))))

    @app.post('/api/sticker/<sid>/find-loop')
    def find_loop(sid):
        s = library.get_sticker(sid)
        if not s or s['source']['kind'] != 'video':
            return jsonify(error='not a video'), 400
        from .media import loop as L
        from .media.frames import load_frames
        frames, fps = load_frames(s['source']['path'], s['source'], 96, 0, None, fps=min(30, s['source'].get('fps') or 30))
        a, b, seam = L.find_loop(frames, fps, TG['video_seconds'])
        return jsonify(start=round(a / fps, 3), end=round(b / fps, 3), seam=round(seam, 2))

    # ---- files ----------------------------------------------------------------------------------------
    @app.get('/api/media/<sid>/<name>')
    def media(sid, name):
        d = library.media_dir(sid)
        name = secure_filename(name)
        if not (d / name).exists():
            abort(404)
        resp = send_from_directory(d, name, conditional=True)
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    @app.get('/api/sticker/<sid>/frame')
    def frame(sid):
        t = float(request.args.get('t', 0))
        try:
            return Response(render.source_frame_png(sid, t), mimetype='image/png')
        except Exception as e:
            return jsonify(error=str(e)), 400

    @app.get('/api/sticker/<sid>/download')
    def download(sid):
        s = library.get_sticker(sid)
        out = (s or {}).get('out') or {}
        if not out.get('file'):
            abort(404)
        path = library.media_dir(sid) / out['file']
        return send_file(path, as_attachment=True, download_name=render.safe_name(s['name']) + path.suffix)

    # ---- packs ----------------------------------------------------------------------------------------
    @app.post('/api/pack')
    def new_pack():
        return jsonify(library.new_pack((request.json or {}).get('title', '')))

    @app.patch('/api/pack/<pid>')
    def patch_pack(pid):
        body = request.json or {}
        fields = {k: v for k, v in body.items() if k in ('title', 'name', 'type', 'stickers', 'needs_repainting')}
        p = library.update_pack(pid, **fields)
        if not p:
            return jsonify(error='not found'), 404
        if 'type' in fields:   # the canvas changed (512 vs 100): every sticker renders again
            for sid in p['stickers']:
                render.schedule_render(sid)
        events.emit('pack', p)
        return jsonify(p)

    @app.post('/api/pack/<pid>/switch')
    def switch_pack(pid):
        p = library.switch_pack(pid)
        return jsonify(p) if p else (jsonify(error='not found'), 404)

    @app.delete('/api/pack/<pid>')
    def delete_pack(pid):
        ok = library.delete_pack(pid, with_stickers=request.args.get('stickers') == '1')
        return jsonify(ok=ok)

    @app.post('/api/pack/<pid>/move')
    def move(pid):
        b = request.json or {}
        p = library.move_stickers(b.get('ids') or [], b.get('to'))
        if b.get('remove'):
            cur = library.current_pack()
            library.update_pack(pid, stickers=[s for s in cur['stickers'] if s not in (b.get('ids') or [])])
        return jsonify(p or {})

    @app.get('/api/pack/<pid>/export')
    def export_pack(pid):
        target = request.args.get('target', 'telegram')
        if target not in TARGETS:
            abort(400)
        zpath, report = export.export_zip(pid, target, progress=lambda i, n, nm: events.emit('export', dict(i=i, n=n, name=nm)))
        return send_file(zpath, as_attachment=True, download_name=os.path.basename(zpath))

    # ---- Telegram -------------------------------------------------------------------------------------
    @app.post('/api/tg/token')
    def tg_token():
        token = (request.json or {}).get('token', '').strip()
        if not token:
            library.save_settings(token='', bot_username=None, bot_name=None)
            return jsonify(ok=True, cleared=True)
        if not telegram.valid_token(token):
            return jsonify(error='That does not look like a bot token (123456789:ABC...)'), 400
        try:
            me = telegram.get_me(token)
        except telegram.TelegramError as e:
            return jsonify(error=e.human()), 400
        library.save_settings(token=token, bot_username=me['username'], bot_name=me.get('first_name'))
        return jsonify(ok=True, bot=dict(username=me['username'], name=me.get('first_name')))

    @app.post('/api/tg/find-user')
    def tg_find_user():
        st = library.settings()
        if not st.get('token'):
            return jsonify(error='Connect a bot first'), 400
        try:
            wh = telegram.webhook_info(st['token'])
            if wh.get('url'):
                return jsonify(error='This bot has a webhook set, so it cannot read messages here. Use a bot made for stickers, or remove the webhook.'), 400
            res = telegram.find_user(st['token'], int(st.get('tg_offset') or 0))
        except telegram.TelegramError as e:
            return jsonify(error=e.human()), 400
        library.save_settings(tg_offset=res['offset'])
        if res['user']:
            u = res['user']
            nm = ' '.join(x for x in (u.get('first_name'), u.get('last_name')) if x) or u.get('username') or str(u['id'])
            library.save_settings(user_id=u['id'], user_name=nm)
            return jsonify(found=True, user_id=u['id'], user_name=nm)
        return jsonify(found=False)

    @app.post('/api/tg/user')
    def tg_user():
        uid = str((request.json or {}).get('user_id', '')).strip()
        if not uid.isdigit():
            return jsonify(error='A Telegram user id is a number'), 400
        library.save_settings(user_id=int(uid), user_name=None)
        return jsonify(ok=True)

    @app.post('/api/tg/check-name')
    def tg_check_name():
        st = library.settings()
        b = request.json or {}
        if not st.get('bot_username'):
            return jsonify(error='Connect a bot first'), 400
        name = telegram.set_name(b.get('slug', ''), st['bot_username'])
        taken = None
        try:
            remote = telegram.get_set(st['token'], name)
            taken = dict(title=remote.get('title'), count=len(remote.get('stickers', [])), type=remote.get('sticker_type'))
        except telegram.TelegramError:
            taken = None
        return jsonify(name=name, taken=taken, link=f'https://t.me/addstickers/{name}')

    @app.post('/api/tg/publish')
    def tg_publish():
        st = library.settings()
        b = request.json or {}
        if not st.get('token') or not st.get('bot_username'):
            return jsonify(error='Connect a bot first'), 400
        if not st.get('user_id'):
            return jsonify(error='Telegram needs to know who owns the set: press Start on your bot'), 400
        pid = b.get('pack') or library.current_pack()['id']
        pack = library.snapshot()['packs'].get(pid)
        if not pack:
            return jsonify(error='no such pack'), 404
        title = (b.get('title') or pack['title'] or 'Stickers').strip()[:64]
        name = telegram.set_name(b.get('slug') or telegram.slug_of(pack.get('name') or '', st['bot_username']) or title, st['bot_username'])
        bad = telegram.check_name(name, st['bot_username'])
        if bad:
            return jsonify(error=bad), 400
        try:
            publish.start(pid, st['token'], st['user_id'], name, title, st['bot_username'],
                          pack.get('type', 'regular'), bool(pack.get('needs_repainting')))
        except RuntimeError as e:
            return jsonify(error=str(e)), 409
        return jsonify(ok=True, name=name)

    @app.post('/api/tg/remote')
    def tg_remote():
        st = library.settings()
        name = (request.json or {}).get('name')
        if not st.get('token') or not name:
            return jsonify(error='no'), 400
        try:
            s = telegram.get_set(st['token'], name)
        except telegram.TelegramError as e:
            return jsonify(error=e.human()), 404
        return jsonify(set=dict(name=s['name'], title=s['title'], type=s.get('sticker_type'),
                                stickers=[dict(file_id=x['file_id'], emoji=x.get('emoji'), video=x.get('is_video'),
                                               w=x.get('width'), h=x.get('height')) for x in s.get('stickers', [])]))

    @app.post('/api/tg/remote/delete')
    def tg_remote_delete():
        st = library.settings()
        b = request.json or {}
        try:
            telegram.delete_sticker(st['token'], b['file_id'])
        except telegram.TelegramError as e:
            return jsonify(error=e.human()), 400
        pack = library.snapshot()['packs'].get(b.get('pack') or '')
        if pack and pack.get('published'):
            pub = pack['published']
            pub['stickers'] = {k: v for k, v in (pub.get('stickers') or {}).items() if v != b['file_id']}
            library.update_pack(pack['id'], published=pub)
        return jsonify(ok=True)

    @app.post('/api/tg/remote/delete-set')
    def tg_delete_set():
        st = library.settings()
        b = request.json or {}
        try:
            telegram.delete_set(st['token'], b['name'])
        except telegram.TelegramError as e:
            return jsonify(error=e.human()), 400
        pack = library.snapshot()['packs'].get(b.get('pack') or '')
        if pack:
            library.update_pack(pack['id'], published=None)
        return jsonify(ok=True)

    @app.post('/api/tg/thumbnail')
    def tg_thumbnail():
        """Make the set icon (100x100) from a sticker of the pack and set it."""
        st = library.settings()
        b = request.json or {}
        pack = library.snapshot()['packs'].get(b.get('pack') or '')
        pub = (pack or {}).get('published')
        if not pub:
            return jsonify(error='Publish the pack first'), 400
        sid = b.get('sticker')
        s = library.get_sticker(sid)
        if not s:
            return jsonify(error='no such sticker'), 404
        try:
            from .media import encode, transform
            is_video = s['source']['kind'] == 'video'
            spec = dict(fmt='webm' if is_video else 'webp', side=100, square=True,
                        bytes=TG['thumb_video_bytes'] if is_video else TG['thumb_static_bytes'], seconds=3.0, fps=30)
            frames, fps, _ = render.pipeline(s, s.get('edit') or {}, spec, is_video)
            d = library.media_dir(sid)
            if is_video:
                p = d / 'icon.webm'
                encode.encode_webm(transform.even(frames), fps, str(p), spec['bytes'])
                telegram.set_thumbnail(st['token'], pub['user_id'], pub['name'], p, 'video')
            else:
                p = d / 'icon.webp'
                encode.encode_still(frames[0], str(p), 'webp', spec['bytes'])
                telegram.set_thumbnail(st['token'], pub['user_id'], pub['name'], p, 'static')
        except telegram.TelegramError as e:
            return jsonify(error=e.human()), 400
        except Exception as e:
            return jsonify(error=str(e)[-200:]), 400
        return jsonify(ok=True)

    # ---- tools ----------------------------------------------------------------------------------------
    @app.post('/api/tools/install-ai')
    def install_ai():
        def run():
            events.emit('install', dict(line='Installing rembg and onnxruntime (a few minutes, ~300 MB)'))
            ok = rembg_bridge.install(lambda line: events.emit('install', dict(line=line)))
            events.emit('install', dict(done=True, ok=ok and rembg_bridge.available()))
        threading.Thread(target=run, daemon=True).start()
        return jsonify(ok=True)

    @app.post('/api/tools/open-folder')
    def open_folder():
        from .config import DATA_DIR
        import subprocess, sys
        try:
            if sys.platform == 'darwin':
                subprocess.Popen(['open', str(DATA_DIR)])
            elif sys.platform == 'win32':
                os.startfile(str(DATA_DIR))  # noqa
            else:
                subprocess.Popen(['xdg-open', str(DATA_DIR)])
        except Exception as e:
            return jsonify(error=str(e)), 400
        return jsonify(ok=True)

    @app.errorhandler(413)
    def too_big(e):
        return jsonify(error='That upload is over 400 MB'), 413

    return app


def _have(path):
    return bool(shutil.which(path) or os.path.exists(path))
