"""Generates high-resolution presentation thumbnail for Entry Strategy Matrix (Active Signals Only)."""
from pathlib import Path
from PIL import Image, ImageDraw


def draw_active_card(draw, x, y, w, h, id_num, title, cat, status="BUY", price="2745.20", time_str="Just now", reason="Kondisi terpenuhi"):
    is_buy = (status == "BUY")
    bg = (16, 45, 35, 255) if is_buy else (48, 20, 24, 255)
    border = (16, 185, 129, 255) if is_buy else (239, 68, 68, 255)
    text_color = (16, 185, 129, 255) if is_buy else (239, 68, 68, 255)
    badge_bg = (16, 185, 129, 255) if is_buy else (239, 68, 68, 255)
    badge_fg = (0, 0, 0, 255) if is_buy else (255, 255, 255, 255)
    badge_text = "▲ BUY" if is_buy else "▼ SELL"

    # Card background
    draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=bg, outline=border, width=2)

    # Top row
    draw.text((x + 12, y + 10), f"#{id_num:02d}", fill=(140, 148, 160, 255))
    draw.text((x + 44, y + 10), cat.upper(), fill=(59, 130, 246, 255))
    draw.text((x + w - 70, y + 10), time_str, fill=(200, 205, 215, 255))

    # Pattern Title (Large, bold)
    draw.text((x + 12, y + 32), title, fill=text_color)

    # Price strip
    sy = y + 58
    draw.rounded_rectangle([x + 12, sy, x + w - 12, sy + 28], radius=5, fill=(10, 12, 15, 200))
    draw.rounded_rectangle([x + 16, sy + 4, x + 72, sy + 24], radius=3, fill=badge_bg)
    draw.text((x + 22, sy + 7), badge_text, fill=badge_fg)
    draw.text((x + w - 90, sy + 7), f"@{price}", fill=(255, 255, 255, 255))

    # Reason snippet
    ry = y + 94
    draw.rounded_rectangle([x + 12, ry, x + w - 12, ry + 24], radius=4, fill=(12, 14, 18, 180))
    draw.text((x + 18, ry + 5), f"[✓] {reason}", fill=(200, 210, 225, 255))

    # Click hint
    draw.text((x + w - 150, y + h - 18), "Klik untuk detail alasan →", fill=(100, 108, 120, 255))


def create_thumbnail(width: int = 1280, height: int = 720) -> Image.Image:
    img = Image.new("RGBA", (width, height), (18, 19, 23, 255))
    draw = ImageDraw.Draw(img)

    # Background grid
    for gy in range(0, height, 40):
        draw.line([(0, gy), (width, gy)], fill=(28, 30, 36, 120), width=1)
    for gx in range(0, width, 40):
        draw.line([(gx, 0), (gx, height)], fill=(28, 30, 36, 120), width=1)

    win_x = 40
    win_y = 40
    win_w = width - 80
    win_h = height - 80
    win_r = 12

    # Drop shadow
    for s in range(12, 0, -2):
        draw.rounded_rectangle(
            [win_x - s, win_y - s, win_x + win_w + s, win_y + win_h + s],
            radius=win_r + s,
            outline=(0, 0, 0, int(25 * (13 - s))),
            width=2,
        )

    # Window frame
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + win_h],
        radius=win_r,
        fill=(20, 22, 27, 255),
        outline=(46, 50, 60, 255),
        width=1,
    )

    # Window Header
    hdr_h = 46
    draw.rounded_rectangle(
        [win_x, win_y, win_x + win_w, win_y + hdr_h],
        radius=win_r,
        fill=(27, 29, 36, 255),
    )
    draw.rectangle([win_x, win_y + hdr_h - 12, win_x + win_w, win_y + hdr_h], fill=(27, 29, 36, 255))
    draw.line([(win_x, win_y + hdr_h), (win_x + win_w, win_y + hdr_h)], fill=(40, 44, 54, 255), width=1)
    draw.text((win_x + win_w - 70, win_y + 14), "−   □   ×", fill=(150, 155, 165, 255))
    draw.text((win_x + 18, win_y + 13), "⚡ ENTRY STRATEGY MATRIX", fill=(255, 255, 255, 255))

    # Port 5558 LIVE badge
    draw.rounded_rectangle([win_x + 270, win_y + 11, win_x + 410, win_y + 35], radius=12, fill=(16, 185, 129, 40), outline=(16, 185, 129, 200), width=1)
    draw.ellipse([win_x + 282, win_y + 20, win_x + 290, win_y + 28], fill=(16, 185, 129, 255))
    draw.text((win_x + 298, win_y + 15), "PORT 5558 LIVE", fill=(16, 185, 129, 255))

    # Symbol & Stats Pills
    draw.rounded_rectangle([win_x + 425, win_y + 11, win_x + 555, win_y + 35], radius=12, fill=(24, 26, 32, 255), outline=(42, 45, 54, 255), width=1)
    draw.text((win_x + 437, win_y + 15), "XAUUSD  2745.20", fill=(255, 255, 255, 255))

    draw.rounded_rectangle([win_x + 570, win_y + 11, win_x + 675, win_y + 35], radius=12, fill=(24, 26, 32, 255), outline=(42, 45, 54, 255), width=1)
    draw.text((win_x + 582, win_y + 15), "SPD: 1.4 pts", fill=(200, 205, 215, 255))

    draw.rounded_rectangle([win_x + 690, win_y + 11, win_x + 795, win_y + 35], radius=12, fill=(24, 26, 32, 255), outline=(42, 45, 54, 255), width=1)
    draw.text((win_x + 702, win_y + 15), "145 ticks/s", fill=(96, 165, 250, 255))

    # Signal Count Badges in Menu Bar
    draw.rounded_rectangle([win_x + 810, win_y + 11, win_x + 915, win_y + 35], radius=12, fill=(16, 185, 129, 35), outline=(16, 185, 129, 180), width=1)
    draw.text((win_x + 822, win_y + 15), "▲ BUY: 2", fill=(16, 185, 129, 255))

    draw.rounded_rectangle([win_x + 925, win_y + 11, win_x + 1030, win_y + 35], radius=12, fill=(239, 68, 68, 35), outline=(239, 68, 68, 180), width=1)
    draw.text((win_x + 937, win_y + 15), "▼ SELL: 1", fill=(239, 68, 68, 255))

    # Filter Bar
    bar_y = win_y + hdr_h + 1
    bar_h = 40
    draw.rectangle([win_x, bar_y, win_x + win_w, bar_y + bar_h], fill=(21, 23, 28, 255))
    draw.line([(win_x, bar_y + bar_h), (win_x + win_w, bar_y + bar_h)], fill=(38, 42, 50, 255), width=1)

    filters = ["Semua Sinyal", "BUY Saja (Hijau)", "SELL Saja (Merah)"]
    fx = win_x + 16
    for i, f_text in enumerate(filters):
        btn_w = len(f_text) * 8 + 14
        active = (i == 0)
        f_bg = (46, 51, 64, 255) if active else (0, 0, 0, 0)
        f_border = (59, 130, 246, 255) if active else (43, 46, 55, 255)
        f_color = (255, 255, 255, 255) if active else (148, 155, 164, 255)
        draw.rounded_rectangle([fx, bar_y + 8, fx + btn_w, bar_y + bar_h - 8], radius=5, fill=f_bg, outline=f_border, width=1)
        draw.text((fx + 8, bar_y + 12), f_text, fill=f_color)
        fx += btn_w + 8

    draw.text((win_x + win_w - 240, bar_y + 12), "3 Sinyal Terpenuhi (Idle Tersembunyi)", fill=(16, 185, 129, 255))

    # Matched Signal Cards (Only active signals shown!)
    card_w = 370
    card_h = 145

    cards_data = [
        (13, "Tick Imbalance", "Tick", "BUY", "2745.30", "Just now", "Dominasi Uptick 85.0% (17 naik vs 3 turun)"),
        (1, "Candlestick Reversal", "Candle", "BUY", "2745.10", "4s ago", "Bullish Engulfing menelan C[1] (Rasio 1.45x)"),
        (4, "Inside Bar Breakout", "Candle", "SELL", "2744.80", "12s ago", "Breakout ke bawah menembus Low Mother Bar"),
    ]

    for idx, (cid, ctitle, ccat, cstat, cpx, ctime, crea) in enumerate(cards_data):
        cx = win_x + 24 + (idx * (card_w + 16))
        cy = bar_y + bar_h + 20
        draw_active_card(draw, cx, cy, card_w, card_h, cid, ctitle, ccat, cstat, cpx, ctime, crea)

    # Floating Pop-up Detail Preview
    pop_w = 420
    pop_h = 240
    pop_x = win_x + 24
    pop_y = bar_y + bar_h + 20 + card_h + 24

    draw.rounded_rectangle([pop_x - 6, pop_y - 6, pop_x + pop_w + 6, pop_y + pop_h + 6], radius=10, fill=(0, 0, 0, 160))
    draw.rounded_rectangle([pop_x, pop_y, pop_x + pop_w, pop_y + pop_h], radius=8, fill=(27, 29, 35, 255), outline=(55, 60, 75, 255), width=2)
    draw.rounded_rectangle([pop_x, pop_y, pop_x + pop_w, pop_y + 36], radius=8, fill=(33, 36, 44, 255))
    draw.rectangle([pop_x, pop_y + 24, pop_x + pop_w, pop_y + 36], fill=(33, 36, 44, 255))
    draw.line([(pop_x, pop_y + 36), (pop_x + pop_w, pop_y + 36)], fill=(45, 50, 62, 255), width=1)
    draw.text((pop_x + 14, pop_y + 10), "#13 Tick Imbalance  |  DETAIL REASON", fill=(255, 255, 255, 255))
    draw.text((pop_x + pop_w - 24, pop_y + 10), "×", fill=(150, 155, 165, 255))

    draw.rounded_rectangle([pop_x + 12, pop_y + 44, pop_x + pop_w - 12, pop_y + 84], radius=6, fill=(20, 21, 26, 255))
    draw.text((pop_x + 20, pop_y + 50), "ARAH: BUY", fill=(16, 185, 129, 255))
    draw.text((pop_x + 140, pop_y + 50), "ENTRY: 2745.30", fill=(255, 255, 255, 255))
    draw.text((pop_x + 280, pop_y + 50), "SPREAD: 1.4", fill=(160, 165, 175, 255))
    draw.text((pop_x + 20, pop_y + 66), "Waktu: 23:10:14.320", fill=(130, 135, 145, 255))

    draw.text((pop_x + 14, pop_y + 96), "📋 Condition Checklist (Alasan Algoritma):", fill=(200, 205, 215, 255))
    reasons = [
        "[✓] Dominasi Uptick Ekstrem: 85.0% (17 naik vs 3 turun)",
        "[✓] Tekanan beli agresif terkonfirmasi pada micro-orderflow",
        "[✓] Spread saat trigger 1.4 pts (dalam batas toleransi)",
    ]
    ry = pop_y + 118
    for rea in reasons:
        draw.text((pop_x + 16, ry), rea, fill=(16, 185, 129, 255))
        ry += 20

    draw.rounded_rectangle([pop_x + pop_w - 95, pop_y + pop_h - 32, pop_x + pop_w - 14, pop_y + pop_h - 10], radius=4, fill=(43, 47, 58, 255))
    draw.text((pop_x + pop_w - 82, pop_y + pop_h - 26), "Tutup (Esc)", fill=(255, 255, 255, 255))

    return img


def main():
    assets_dir = Path(__file__).parent.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    img = create_thumbnail(1280, 720)
    out_path = assets_dir / "thumbnail.png"
    img.save(out_path, "PNG")
    print(f"Updated thumbnail at: {out_path}")


if __name__ == "__main__":
    main()
