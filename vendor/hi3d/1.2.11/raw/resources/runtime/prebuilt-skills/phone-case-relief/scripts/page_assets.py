"""Versioned local asset input and explicit HTML template composition."""
import base64
import hashlib
import html
from pathlib import Path, PurePosixPath
import re
from string import Template


def read_asset(root, relative, *, expected_sha256=None):
    """Read one nonempty local asset, rejecting traversal and escaped symlinks."""
    root=Path(root).resolve();relative=PurePosixPath(relative)
    if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
        raise ValueError('Asset path must be relative and inside its root')
    path=(root/relative).resolve()
    if not path.is_relative_to(root):raise ValueError('Asset symlink leaves root')
    raw=path.read_bytes()
    if not raw:raise ValueError('Empty page asset: '+str(relative))
    record={'file':relative.as_posix(),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if expected_sha256 is not None and record['sha256']!=expected_sha256:
        raise ValueError('Asset changed since manifest: '+str(relative))
    return raw,record


def encode_asset(raw):
    return base64.b64encode(raw).decode('ascii')


def render_template(template, replacements, *, syntax='tokens'):
    """Pure substitution of caller-escaped fragments; never execute templates.

    tokens: literal __KEY__ markers, one simultaneous substitution; dollar:
    string.Template, used by the existing offline print-kit viewer.
    """
    if syntax=='dollar':return Template(template).substitute(replacements)
    if syntax!='tokens':raise ValueError('Unsupported template syntax')
    missing=[token for token in replacements if token not in template]
    if missing:raise ValueError('Missing template token: '+', '.join(missing))
    pattern=re.compile('|'.join(re.escape(k) for k in sorted(replacements,key=len,reverse=True)))
    return pattern.sub(lambda match:replacements[match.group()],template) if replacements else template


def image_figure(raw, label, *, mime='image/png'):
    if mime not in ('image/png','image/jpeg','image/webp'):raise ValueError('Unsupported embedded image format')
    label=html.escape(label,quote=True)
    return f'<figure><img alt="{label}" src="data:{mime};base64,{encode_asset(raw)}"><figcaption>{label}</figcaption></figure>'
