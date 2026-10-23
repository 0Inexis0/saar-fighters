#!/usr/bin/env python3
"""Package a large ISO as GitHub-sized parts with verified download helpers."""
import argparse
import hashlib
from pathlib import Path
import textwrap

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
parser.add_argument('--tag', required=True)
args = parser.parse_args()
isos = list(args.directory.glob('*.iso'))
if len(isos) != 1:
    raise SystemExit('Expected exactly one ISO in the release directory')
iso = isos[0]
out = args.directory / 'github'
out.mkdir(exist_ok=True)
name = iso.name
sha = hashlib.file_digest(iso.open('rb'), 'sha256').hexdigest()
base = f'https://github.com/0Inexis0/saar-fighters-updates/releases/download/{args.tag}'
parts = []
with iso.open('rb') as source:
    index = 1
    while True:
        data = source.read(8 * 1024 * 1024)
        if not data:
            break
        part = out / f'{name}.part{index:02d}'
        remaining = 1600 * 1024 * 1024
        with part.open('wb') as target:
            while data:
                target.write(data)
                remaining -= len(data)
                if remaining == 0:
                    break
                data = source.read(min(8 * 1024 * 1024, remaining))
        parts.append(part.name)
        index += 1
(out / 'SHA256SUMS').write_text(f'{sha}  {name}\n')
(out / 'PARTS-SHA256SUMS').write_text(''.join(
    f'{hashlib.file_digest((out / part).open("rb"), "sha256").hexdigest()}  {part}\n' for part in parts))
shell = '''#!/usr/bin/env bash
# Download and assemble the official ISO. No root access, no disk writing.
set -euo pipefail
name='@NAME@'
expected='@SHA@'
base='@BASE@'
[[ ! -e "$name" ]] || { echo "Datei existiert bereits: $name"; exit 1; }
stage=$(mktemp -d .saar-download.XXXXXX)
trap 'rm -rf -- "$stage"' EXIT
parts=(@PARTS@)
for part in "${parts[@]}"; do
    echo "Lade $part …"
    curl --fail --location --retry 3 --proto '=https' --tlsv1.2 "$base/$part" -o "$stage/$part"
done
for part in "${parts[@]}"; do cat "$stage/$part"; done > "$stage/$name"
echo 'Prüfe vollständige ISO …'
if command -v sha256sum >/dev/null; then
    actual=$(sha256sum "$stage/$name" | cut -d ' ' -f 1)
else
    actual=$(shasum -a 256 "$stage/$name" | cut -d ' ' -f 1)
fi
[[ $actual == "$expected" ]] || { echo 'Prüfsumme stimmt nicht! Bitte erneut herunterladen.'; exit 1; }
mv -- "$stage/$name" "$name"
echo "Fertig: $PWD/$name"
echo 'Diese ISO jetzt mit deinem USB-Image-Programm auf den Stick schreiben.'
'''
ps = '''# Download and assemble the official ISO. No admin rights, no disk writing.
$ErrorActionPreference = 'Stop'
$name = '@NAME@'
$expected = '@SHA@'
$base = '@BASE@'
$destination = Join-Path (Get-Location) $name
if (Test-Path $destination) { throw "Datei existiert bereits: $destination" }
$stage = Join-Path (Get-Location) ('.saar-download-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $parts = @(@PSPARTS@)
    foreach ($part in $parts) {
        Write-Host "Lade $part ..."
        Invoke-WebRequest -UseBasicParsing -Uri "$base/$part" -OutFile (Join-Path $stage $part)
    }
    $assembled = Join-Path $stage $name
    $output = [IO.File]::Create($assembled)
    try {
        foreach ($part in $parts) {
            $inputFile = [IO.File]::OpenRead((Join-Path $stage $part))
            try { $inputFile.CopyTo($output) } finally { $inputFile.Dispose() }
        }
    } finally { $output.Dispose() }
    Write-Host 'Pruefe vollstaendige ISO ...'
    if ((Get-FileHash $assembled -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw 'Pruefsumme stimmt nicht. Bitte erneut herunterladen.'
    }
    Move-Item -LiteralPath $assembled -Destination $destination
    Write-Host "Fertig: $destination"
    Write-Host 'Diese ISO jetzt mit deinem USB-Image-Programm auf den Stick schreiben.'
} finally { Remove-Item -LiteralPath $stage -Recurse -Force }
'''
for filename, template in [('download-iso.sh', shell), ('download-iso.ps1', ps)]:
    text = textwrap.dedent(template).replace('@NAME@', name).replace('@SHA@', sha).replace('@BASE@', base)
    text = text.replace('@PARTS@', ' '.join("'" + p + "'" for p in parts))
    text = text.replace('@PSPARTS@', ', '.join("'" + p + "'" for p in parts))
    (out / filename).write_text(text)
(out / 'download-iso.sh').chmod(0o755)
print(f'Prepared {len(parts)} parts and download helpers in {out}')
