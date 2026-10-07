"""ZIP exports: the pack for Telegram (the files as rendered) or re-encoded for another platform."""
import os
import tempfile
import zipfile

from . import library, render
from .config import TARGETS


def export_zip(pid, target='telegram', progress=None):
    db = library.snapshot()
    pack = db['packs'][pid]
    stickers = [db['stickers'][s] for s in pack['stickers'] if s in db['stickers']]
    tmpdir = tempfile.mkdtemp(prefix='emosticker-export-')
    zpath = os.path.join(tmpdir, f'{render.safe_name(pack["title"])}-{target}.zip')
    report = []
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for i, st in enumerate(stickers):
            name = f'{i + 1:02d}-{render.safe_name(st["name"])}'
            try:
                if target == 'telegram':
                    out = st.get('out') or {}
                    if not out.get('file'):
                        continue
                    src = library.media_dir(st['id']) / out['file']
                    z.write(src, f'{name}{src.suffix}')
                    report.append(dict(name=name, bytes=out.get('bytes'), ok=bool(out.get('ready'))))
                else:
                    path, v = render.export_file(st['id'], target, tmpdir, pack.get('type', 'regular'))
                    z.write(path, f'{name}{os.path.splitext(path)[1]}')
                    os.remove(path)
                    spec = TARGETS[target]['video' if st['source']['kind'] == 'video' else 'static']
                    report.append(dict(name=name, bytes=v['bytes'], ok=v['bytes'] <= spec['bytes']))
            except Exception as e:
                report.append(dict(name=name, error=str(e)[-200:], ok=False))
            if progress:
                progress(i + 1, len(stickers), name)
        lines = [f'{pack["title"]} exported for {TARGETS[target]["label"]}', '']
        for r in report:
            lines.append(f'{r["name"]}: ' + (f'{r["bytes"]} bytes' if r.get('bytes') else r.get('error', '')) + ('' if r['ok'] else '  (over the limit)'))
        z.writestr('README.txt', '\n'.join(lines))
    return zpath, report
