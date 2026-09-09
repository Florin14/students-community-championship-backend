import base64
import io

from fastapi import status
from PIL import Image

from project_helpers.error import Error
from project_helpers.exceptions import ErrorException


def process_and_convert_image_to_base64(value: str, max_size: int = 316) -> bytes:
    """Decode a base64 image, downscale it and return base64 bytes for storage."""
    try:
        raw = value.split(",", 1)[1] if "," in value else value
        image = Image.open(io.BytesIO(base64.b64decode(raw)))
        image.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue())
    except Exception:
        raise ErrorException(
            Error.INVALID_IMAGE, status_code=status.HTTP_400_BAD_REQUEST
        )
