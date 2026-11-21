"""Draw the Database Explorer logo and write every icon file the app needs.

    backend\\venv\\Scripts\\python.exe packaging\\make_icons.py

Outputs:
    packaging/icon.ico              Windows .exe icon (16-256 px)
    packaging/logo.png              1024 px, for the GitHub page / README
    frontend/public/favicon.ico     browser tab icon
    frontend/public/logo-192.png    logo shown in the app (sidebar, connect page)
"""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SS = 4                 # draw 4x larger, then shrink: smooth edges
N = 1024 * SS


def s(*v):
    """Scale 1024-unit coordinates to the supersampled canvas."""
    return [round(x * SS) for x in v]


def gradient(top, bottom):
    g = Image.new("RGBA", (1, 256))
    for y in range(256):
        t = y / 255
        g.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    return g.resize((N, N))


def draw_logo():
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))

    # Rounded-square background, indigo gradient
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).rounded_rectangle(s(0, 0, 1024, 1024), radius=230 * SS, fill=255)
    img.paste(gradient((99, 102, 241), (55, 48, 163)), (0, 0), mask)

    d = ImageDraw.Draw(img)
    # Database cylinder: body, bottom cap, separators, top face
    left, right, top, bottom, h = 200, 640, 250, 720, 140
    body = (224, 231, 255)
    d.rectangle(s(left, top, right, bottom), fill=body)
    d.ellipse(s(left, bottom - h / 2, right, bottom + h / 2), fill=body)
    for y in (407, 563):
        d.arc(s(left, y - h / 2, right, y + h / 2), 0, 180, fill=(99, 102, 241), width=26 * SS)
    d.ellipse(s(left, top - h / 2, right, top + h / 2), fill=(255, 255, 255))

    # Magnifying glass: tinted lens, amber ring, handle
    cx, cy, r = 690, 650, 165
    lens = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    ImageDraw.Draw(lens).ellipse(s(cx - r, cy - r, cx + r, cy + r), fill=(165, 243, 252, 110))
    img = Image.alpha_composite(img, lens)
    d = ImageDraw.Draw(img)
    amber, amber_dark = (251, 191, 36), (245, 158, 11)
    d.line(s(cx + 120, cy + 120, 875, 835), fill=amber_dark, width=92 * SS)
    d.ellipse(s(875 - 46, 835 - 46, 875 + 46, 835 + 46), fill=amber_dark)  # round handle end
    ring = 54
    d.ellipse(s(cx - r, cy - r, cx + r, cy + r), outline=amber, width=ring * SS)
    # Shine on the lens
    d.arc(s(cx - r + 70, cy - r + 70, cx + r - 70, cy + r - 70), 200, 260,
          fill=(255, 255, 255), width=22 * SS)
    return img


def main():
    big = draw_logo().resize((1024, 1024), Image.LANCZOS)
    (ROOT / "frontend" / "public").mkdir(parents=True, exist_ok=True)
    big.save(ROOT / "packaging" / "logo.png")
    big.resize((192, 192), Image.LANCZOS).save(ROOT / "frontend" / "public" / "logo-192.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    big.save(ROOT / "packaging" / "icon.ico", sizes=sizes)
    big.save(ROOT / "frontend" / "public" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    print("Icons written.")


if __name__ == "__main__":
    main()
