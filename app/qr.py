"""QR codes: the plain black-and-white one, and styled ones (colours and a logo in the centre).

PNG and SVG are both drawn from the same grid of squares, so they always look the same. A logo
needs the strongest error correction (H) so the code still scans with its middle covered, and it
is kept small. Colours must keep a strong contrast, dark on light, or phones will not read them.
"""

import base64
import io
import re
from dataclasses import dataclass

import qrcode
from PIL import Image, ImageDraw, UnidentifiedImageError
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_M

DEFAULT_FG = "#000000"
DEFAULT_BG = "#ffffff"
MIN_CONTRAST = 4.0
BOX = 10  # pixels per square in a PNG
BORDER = 4  # the quiet zone, in squares
LOGO_SHARE = 0.22  # the logo's side as a share of the code's side
LOGO_PAD = 0.012  # extra margin around the logo, as a share of the code's side
MAX_LOGO_BYTES = 1_000_000
LOGO_PIXELS = 256  # logos are stored at most this wide and tall
_HEX = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


@dataclass(frozen=True)
class QrStyle:
    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG
    logo: bytes | None = None  # a small PNG

    @classmethod
    def of(cls, link) -> "QrStyle":
        return cls(link.qr_fg or DEFAULT_FG, link.qr_bg or DEFAULT_BG, link.qr_logo or None)

    @property
    def is_default(self) -> bool:
        return (self.fg, self.bg, self.logo) == (DEFAULT_FG, DEFAULT_BG, None)

    @property
    def version(self) -> str:
        """Changes whenever the look changes, so a browser never shows a stale preview."""
        return f"{self.fg[1:]}{self.bg[1:]}{len(self.logo or b'')}"


# ---- colours ------------------------------------------------------------------------------


def parse_color(raw: str | None) -> str:
    """'#abc', 'ABCDEF' ... -> '#aabbcc'. ValueError for anything else."""
    match = _HEX.fullmatch((raw or "").strip())
    if not match:
        raise ValueError("Pick colours as #RRGGBB values, for example #1a2b3c.")
    digits = match.group(1).lower()
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits


def luminance(color: str) -> float:
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def check_colors(fg: str, bg: str) -> None:
    """The code must be darker than its background, with enough contrast to scan."""
    if luminance(fg) >= luminance(bg) or contrast_ratio(fg, bg) < MIN_CONTRAST:
        raise ValueError(
            "The colours need more contrast so phones can scan the code. "
            "Use a darker code colour on a lighter background."
        )


# ---- the logo -------------------------------------------------------------------------------


def process_logo(data: bytes) -> bytes:
    """A small, safe PNG made from an uploaded picture. Raises ValueError if it is not one."""
    problem = "The logo must be a PNG, JPG or WebP picture up to 1 MB."
    if not data or len(data) > MAX_LOGO_BYTES:
        raise ValueError(problem)
    try:
        with Image.open(io.BytesIO(data)) as picture:
            if picture.format not in ("PNG", "JPEG", "WEBP"):
                raise ValueError(problem)
            picture.load()
            logo = picture.convert("RGBA")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError(problem) from None
    logo.thumbnail((LOGO_PIXELS, LOGO_PIXELS))
    out = io.BytesIO()
    logo.save(out, format="PNG", optimize=True)
    return out.getvalue()


# ---- drawing --------------------------------------------------------------------------------


def grid(text: str, with_logo: bool) -> list[list[bool]]:
    """The squares of the code, quiet zone included."""
    code = qrcode.QRCode(
        error_correction=ERROR_CORRECT_H if with_logo else ERROR_CORRECT_M,
        box_size=BOX, border=BORDER,
    )
    code.add_data(text)
    code.make(fit=True)
    return code.get_matrix()


def _logo_box(size: int) -> tuple[float, float, float]:
    """(left/top, logo side, padded side) in squares, centred in a code `size` squares wide."""
    side = size * LOGO_SHARE
    plate = side + 2 * size * LOGO_PAD
    return (size - side) / 2, side, plate


def png_bytes(text: str, style: QrStyle = QrStyle()) -> bytes:
    cells = grid(text, style.logo is not None)
    size = len(cells)
    image = Image.new("RGB", (size * BOX, size * BOX), style.bg)
    draw = ImageDraw.Draw(image)
    for y, row in enumerate(cells):
        for x, dark in enumerate(row):
            if dark:
                draw.rectangle(
                    (x * BOX, y * BOX, (x + 1) * BOX - 1, (y + 1) * BOX - 1), fill=style.fg
                )
    if style.logo:
        start, side, plate = _logo_box(size)
        pad = (plate - side) / 2
        left, top = start * BOX, start * BOX
        near, far = (-pad) * BOX, (side + pad) * BOX
        draw.rounded_rectangle(
            (left + near, top + near, left + far, top + far), radius=BOX, fill=style.bg
        )
        with Image.open(io.BytesIO(style.logo)) as picture:
            logo = picture.convert("RGBA").resize((round(side * BOX),) * 2, Image.LANCZOS)
        image.paste(logo, (round(left), round(top)), logo)
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def svg_text(text: str, style: QrStyle = QrStyle()) -> str:
    cells = grid(text, style.logo is not None)
    size = len(cells)
    runs = []  # one horizontal bar for every run of dark squares in a row
    for y, row in enumerate(cells):
        x = 0
        while x < size:
            if row[x]:
                start = x
                while x < size and row[x]:
                    x += 1
                runs.append(f"M{start} {y}h{x - start}v1h-{x - start}z")
            else:
                x += 1
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {size} {size}" width="{size * BOX}" height="{size * BOX}" '
        f'shape-rendering="crispEdges" role="img">',
        f'<rect width="{size}" height="{size}" fill="{style.bg}"/>',
        f'<path fill="{style.fg}" d="{"".join(runs)}"/>',
    ]
    if style.logo:
        start, side, plate = _logo_box(size)
        pad = (plate - side) / 2
        picture = base64.b64encode(style.logo).decode("ascii")
        parts.append(
            f'<rect x="{start - pad:.3f}" y="{start - pad:.3f}" width="{plate:.3f}" '
            f'height="{plate:.3f}" rx="1" fill="{style.bg}"/>'
            f'<image x="{start:.3f}" y="{start:.3f}" width="{side:.3f}" height="{side:.3f}" '
            f'href="data:image/png;base64,{picture}" '
            f'xlink:href="data:image/png;base64,{picture}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)
