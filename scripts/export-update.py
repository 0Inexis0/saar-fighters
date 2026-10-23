#!/usr/bin/env python3
"""Export only tracked runtime files, never Git history or local build data."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEST = Path(sys.argv[1]).resolve()
if DEST == ROOT or ROOT in DEST.parents or not (DEST / '.git').exists():
    raise SystemExit('Destination must be a separate checked-out update repository')
for name in ('app', 'system', 'installer'):
    target = DEST / name
    if target.exists():
        shutil.rmtree(target)
paths = subprocess.check_output(['git', 'ls-files', '-z', '--', 'app', 'system', 'installer', 'LICENSE'], cwd=ROOT).decode().split('\0')
for name in filter(None, paths):
    source = ROOT / name
    if source.is_symlink() or not source.is_file():
        raise SystemExit(f'Only regular tracked runtime files may be published: {name}')
    if any(part in ('__pycache__', '.git') or part.startswith('credentials') for part in source.relative_to(ROOT).parts):
        raise SystemExit(f'Unexpected runtime file: {name}')
    target = DEST / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(source.stat().st_mode & 0o777)
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
(DEST / 'source-revision').write_text(revision + '\n')
(DEST / 'README.md').write_text('''# Saar-Fighters OS Updates

Öffentliche Laufzeitdateien für den Update-Button von Saar-Fighters OS.
Der Download benötigt weder einen GitHub-Account noch einen Schlüssel.

Dieses Repository enthält nur die ausgelieferte Oberfläche, Taskleiste,
Designs, Installer und Systemhelfer. Entwicklungshistorie, Tests,
VM-Dateien und Zugangsdaten werden nicht veröffentlicht.

Updates auf dem Vereinsrechner über **Updates → Update starten** installieren.
Nach erfolgreichem Abschluss neu starten. Bestehende ältere Installationen
benötigen einmalig den neuen Update-Helfer beziehungsweise eine neue ISO.

`source-revision` bezeichnet den geprüften Entwicklungsstand dieses Pakets.
Lizenz: siehe LICENSE; Vereinslogo gemäß dortigem Bildhinweis.
''')
print(f'Runtime export prepared from {revision[:12]}')
