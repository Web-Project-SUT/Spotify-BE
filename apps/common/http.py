import re

from django.http import FileResponse, HttpResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


def range_file_response(
    file_handle, content_type, *, request=None, as_attachment=False, filename=None
):
    """Serve a file-like object, honouring a `Range: bytes=a-b` request header.

    Neither `django.views.static.serve` nor `FileResponse` implements HTTP
    Range, so without this a player's seek bar re-downloads from byte 0 on
    every seek. Falls back to a plain 200 when no Range header is present.
    """
    file_handle.open("rb")
    size = file_handle.size
    filename = filename or getattr(file_handle, "name", "").rsplit("/", 1)[-1]
    range_header = request.META.get("HTTP_RANGE") if request else None
    match = _RANGE_RE.match(range_header) if range_header else None

    if not match:
        response = FileResponse(file_handle, content_type=content_type)
        response["Accept-Ranges"] = "bytes"
        if as_attachment:
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    start_s, end_s = match.groups()
    start = int(start_s) if start_s else 0
    end = int(end_s) if end_s else size - 1
    end = min(end, size - 1)
    length = end - start + 1

    file_handle.seek(start)
    response = HttpResponse(file_handle.read(length), status=206, content_type=content_type)
    response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Content-Length"] = str(length)
    response["Accept-Ranges"] = "bytes"
    if as_attachment:
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
