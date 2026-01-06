"""
Generate synthetic "scanned" (image-only) PDFs to regression-test OCR.

Outputs (relative to repo root):
- tests/fixtures/scanned_pricing_test.pdf
- tests/fixtures/scanned_nda_test.pdf

These PDFs have NO text layer; OCR must be used to extract content.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    raise SystemExit("PyMuPDF (fitz) is required to generate scanned PDFs") from e


OUT_DIR = Path(__file__).resolve().parent


def _make_text_image(text: str, *, width: int = 1654, height: int = 2339) -> Image.Image:
    """
    Create a white page image with black text. (roughly A4 at ~200dpi)
    """
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Prefer a common font; fall back to default bitmap font.
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    margin_x, margin_y = 80, 80
    max_width = width - 2 * margin_x

    # Simple word wrap
    lines = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        line = words[0]
        for w in words[1:]:
            trial = f"{line} {w}"
            w_px = draw.textlength(trial, font=font)
            if w_px <= max_width:
                line = trial
            else:
                lines.append(line)
                line = w
        lines.append(line)

    y = margin_y
    line_h = int(getattr(font, "size", 28) * 1.6)
    for ln in lines:
        draw.text((margin_x, y), ln, fill="black", font=font)
        y += line_h
        if y > height - margin_y - line_h:
            break

    return img


def _image_to_pdf(img: Image.Image, out_pdf: Path) -> None:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Save temporary PNG next to the output PDF
    tmp_png = out_pdf.with_suffix(".png")
    img.save(tmp_png, format="PNG")

    # Create 1-page PDF with the image
    doc = fitz.open()
    page = doc.new_page(width=img.width, height=img.height)
    rect = fitz.Rect(0, 0, img.width, img.height)
    page.insert_image(rect, filename=str(tmp_png))
    doc.save(str(out_pdf))
    doc.close()

    try:
        tmp_png.unlink(missing_ok=True)  # py3.8+: missing_ok supported on 3.8?
    except TypeError:
        if tmp_png.exists():
            tmp_png.unlink()


def main() -> None:
    pricing_text = (
        "SCANNED PRICING TEST DOCUMENT\n\n"
        "WEEDING\n"
        "Weed out beds, curbs, walkways, etc.\n"
        "T&M (Time and Material) @ $55.00 per man, per man hour, plus dumping fees.\n\n"
        "SEASONAL CONTRACT PRICE: $15,000.00\n"
    )

    nda_text = (
        "SCANNED NDA TEST DOCUMENT\n\n"
        "This Non-Disclosure Agreement is between:\n"
        "Acme Industries, Inc. (\"Acme\")\n"
        "and\n"
        "Beta Fire & Security, LLC (\"Beta\").\n\n"
        "Expiration Date: July 31, 2028\n"
    )

    pricing_img = _make_text_image(pricing_text)
    nda_img = _make_text_image(nda_text)

    _image_to_pdf(pricing_img, OUT_DIR / "scanned_pricing_test.pdf")
    _image_to_pdf(nda_img, OUT_DIR / "scanned_nda_test.pdf")

    print("Generated:")
    print(f"- {OUT_DIR / 'scanned_pricing_test.pdf'}")
    print(f"- {OUT_DIR / 'scanned_nda_test.pdf'}")


if __name__ == "__main__":
    main()
