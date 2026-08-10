"""
uploads/routes.py — Serve files stored in GridFS
"""
from flask import Response, abort
from sallio.uploads import bp
from sallio.storage import get_file


@bp.route('/<file_id>')
def serve(file_id):
    """Stream a GridFS file by its ID."""
    result = get_file(file_id)
    if result is None:
        abort(404)

    data, content_type, filename = result
    return Response(
        data,
        status=200,
        mimetype=content_type,
        headers={
            'Content-Disposition': f'inline; filename="{filename}"',
            'Cache-Control': 'public, max-age=31536000, immutable'
        }
    )
