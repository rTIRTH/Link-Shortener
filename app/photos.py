"""Profile photos. The browser crops the picture, but we never trust it: every upload is
re-checked and re-encoded here (which also removes hidden data such as GPS location)."""
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 25_000_000  # refuse "decompression bombs": tiny files that unpack to huge images
SIZE = 256
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


class PhotoError(ValueError):
    """The upload cannot be used. The message is shown to the person (and translated)."""


def normalise(data: bytes) -> bytes:
    """Return a clean 256x256 JPEG made from the upload, or raise PhotoError."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoError("The photo is too large. Please choose one under 2 MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:  # reads only the header
            image_format, (width, height) = probe.format, probe.size
        if image_format not in ALLOWED_FORMATS:
            raise PhotoError(
                "That file is not a valid photo. Please use a JPEG, PNG or WebP image."
            )
        if width * height > MAX_PIXELS:
            raise PhotoError("That photo's dimensions are too large. Please choose a smaller one.")
        with Image.open(io.BytesIO(data)) as image:
            image.load()  # decode everything now, so broken or cut-off files fail here
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA", "P"):  # see-through parts become white
                image = image.convert("RGBA")
                flat = Image.new("RGB", image.size, "white")
                flat.paste(image, mask=image.getchannel("A"))
                image = flat
            else:
                image = image.convert("RGB")
            image = ImageOps.fit(image, (SIZE, SIZE), Image.LANCZOS)  # centre-crop + resize
    except PhotoError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise PhotoError(
            "That file is not a valid photo. Please use a JPEG, PNG or WebP image."
        ) from None
    out = io.BytesIO()
    image.save(out, "JPEG", quality=88, optimize=True)  # a fresh file: no EXIF, no metadata
    return out.getvalue()
