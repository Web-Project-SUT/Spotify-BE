import os
from collections.abc import Iterable
from uuid import uuid4

from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify


def upload_filename(filename: str) -> str:
    """Slugified stem + short random suffix + lowercased ext."""
    stem, ext = os.path.splitext(filename)
    slug = slugify(stem)[:40] or "file"
    return f"{slug}-{uuid4().hex[:8]}{ext.lower()}"


def replace_files(instance, files: dict[str, UploadedFile]) -> None:
    """Delete the outgoing blobs, attach the new ones, save once."""
    for field_name, upload in files.items():
        old = getattr(instance, field_name)
        if old:
            old.delete(save=False)
        setattr(instance, field_name, upload)
    instance.save()


def clear_files(instance, field_names: Iterable[str]) -> None:
    """Delete blobs from storage and null the fields."""
    for field_name in field_names:
        old = getattr(instance, field_name)
        if old:
            old.delete(save=False)
        setattr(instance, field_name, None)
    instance.save()
