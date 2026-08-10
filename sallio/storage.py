"""
storage.py — Sallio File Storage Layer
=======================================
Handles all file uploads using MongoDB GridFS.
Every file is validated before storage:
  - Whitelisted extensions only
  - File size limit enforced
  - Magic bytes verified (prevents renamed malicious files)
  - Filename sanitised

GridFS stores files directly in MongoDB, so there are no filesystem
persistence issues on Render or any other cloud host.
"""

import io
import os
import re
from bson.objectid import ObjectId
from sallio.db import get_db

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024   # 2 MB

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

# Magic byte signatures for allowed image types
# Key: bytes prefix, Value: MIME type
_IMAGE_SIGNATURES = {
    b'\xff\xd8\xff':                    'image/jpeg',   # JPEG
    b'\x89PNG\r\n\x1a\n':              'image/png',    # PNG
    b'RIFF':                            'image/webp',   # WebP (needs extra check)
}

# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def _get_extension(filename: str) -> str:
    """Return lowercased file extension without the dot."""
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[-1].lower()


def _sanitise_filename(filename: str) -> str:
    """Remove any path components and dangerous characters from a filename."""
    # Strip path separators
    filename = os.path.basename(filename)
    # Keep only alphanumeric, dots, hyphens, underscores
    filename = re.sub(r'[^\w.\-]', '_', filename)
    # Prevent hidden files
    filename = filename.lstrip('.')
    return filename or 'upload'


def _detect_mime(header_bytes: bytes) -> str | None:
    """
    Check the first 12 bytes against known image signatures.
    Returns the MIME type string, or None if not recognised.
    """
    for sig, mime in _IMAGE_SIGNATURES.items():
        if header_bytes.startswith(sig):
            # Extra check for WebP: bytes 8-12 must be 'WEBP'
            if mime == 'image/webp':
                if len(header_bytes) >= 12 and header_bytes[8:12] == b'WEBP':
                    return mime
                return None
            return mime
    return None


def validate_image(file_storage) -> tuple[bool, str]:
    """
    Validate a Werkzeug FileStorage object as a safe image.

    Returns:
        (True, '')          — valid file
        (False, reason)     — invalid, with human-readable reason
    """
    if not file_storage or not file_storage.filename:
        return False, 'No file provided.'

    ext = _get_extension(file_storage.filename)
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        return False, f'File type not allowed. Accepted formats: {allowed.upper()}.'

    # Read the entire file into memory for size + magic-byte check
    file_storage.seek(0)
    data = file_storage.read()
    file_storage.seek(0)   # Reset so the caller can read again

    if len(data) == 0:
        return False, 'The uploaded file is empty.'

    if len(data) > MAX_IMAGE_SIZE_BYTES:
        max_mb = MAX_IMAGE_SIZE_BYTES / (1024 * 1024)
        return False, f'File is too large. Maximum size is {max_mb:.0f} MB.'

    # Magic-byte check — the critical security gate
    mime = _detect_mime(data[:12])
    if mime is None:
        return False, 'File content does not match an allowed image format. Upload may be corrupted or is a renamed file.'

    return True, ''


# ---------------------------------------------------------------------------
# GridFS Storage Operations
# ---------------------------------------------------------------------------

def save_file(file_storage, category: str = 'logo', business_id: str = None) -> str:
    """
    Save a validated FileStorage object to GridFS.

    Args:
        file_storage : Werkzeug FileStorage (already validated)
        category     : logical category tag stored in metadata (e.g. 'logo')
        business_id  : the owning business's ID string

    Returns:
        The GridFS file _id as a string (store this in MongoDB business doc).
    """
    import gridfs
    db = get_db()
    fs = gridfs.GridFS(db)

    file_storage.seek(0)
    data = file_storage.read()

    ext = _get_extension(file_storage.filename)
    safe_name = _sanitise_filename(file_storage.filename)
    content_type = _detect_mime(data[:12]) or 'application/octet-stream'

    file_id = fs.put(
        data,
        filename=safe_name,
        content_type=content_type,
        metadata={
            'category': category,
            'business_id': str(business_id) if business_id else None,
        }
    )
    return str(file_id)


def get_file(file_id: str):
    """
    Retrieve a file from GridFS by its string ID.

    Returns:
        (bytes, content_type, filename)  or  None if not found.
    """
    import gridfs
    db = get_db()
    fs = gridfs.GridFS(db)

    try:
        grid_out = fs.get(ObjectId(file_id))
        data = grid_out.read()
        content_type = grid_out.content_type or 'application/octet-stream'
        filename = grid_out.filename or 'file'
        return data, content_type, filename
    except Exception:
        return None


def delete_file(file_id: str) -> bool:
    """
    Delete a file from GridFS by its string ID.
    Returns True on success, False if not found.
    """
    import gridfs
    db = get_db()
    fs = gridfs.GridFS(db)

    try:
        fs.delete(ObjectId(file_id))
        return True
    except Exception:
        return False
