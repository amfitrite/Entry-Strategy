"""Generates ultra high-resolution sleek application icon for Entry Strategy Matrix."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter


def create_entry_strategy_icon(size: int = 512) -> Image.Image:
    # 2x supersampling for razor sharp vector rendering
    ss = size * 2
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background Squircle
    pad = int(ss * 0.06)
    radius = int(ss * 0.22)

    # Outer ambient glow (Electric Blue & Amber)
    for g in range(6, 0, -1):
        alpha = int(14 * (7 - g))
        draw.rounded_rectangle(
            [pad - g * 3, pad - g * 3, ss - pad + g * 3, ss - pad + g * 3],
            radius=radius + g * 2,
            outline=(59, 130, 246, alpha),
            width=2,
        )

    # Dark metallic gradient fill
    for y in range(pad, ss - pad):
        factor = (y - pad) / (ss - 2 * pad)
        # Gradient from #1e2128 to #0f1013
        r = int(30 * (1 - factor) + 14 * factor)
        g = int(33 * (1 - factor) + 16 * factor)
        b = int(42 * (1 - factor) + 20 * factor)
        draw.line([(pad, y), (ss - pad, y)], fill=(r, g, b, 255))

    # Mask to squircle shape
    mask = Image.new("L", (ss, ss), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([pad, pad, ss - pad, ss - pad], radius=radius, fill=255)

    base = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    base.paste(img, (0, 0), mask)
    draw = ImageDraw.Draw(base)

    # Sleek border outline
    draw.rounded_rectangle(
        [pad, pad, ss - pad, ss - pad],
        radius=radius,
        outline=(59, 130, 246, 210),
        width=int(ss * 0.015),
    )

    # 2. Subtle Matrix Background Grid Pattern
    grid_start = int(ss * 0.16)
    grid_end = int(ss * 0.84)
    step = int(ss * 0.11)
    for gx in range(grid_start, grid_end, step):
        draw.line([(gx, grid_start), (gx, grid_end)], fill=(45, 52, 66, 60), width=2)
    for gy in range(grid_start, grid_end, step):
        draw.line([(grid_start, gy), (grid_end, gy)], fill=(45, 52, 66, 60), width=2)

    # 3. High-Tech Dynamic Waveform / Tick Impulse
    mid_y = int(ss * 0.52)
    wave_pts = []
    for x in range(grid_start, grid_end + 1, 8):
        t = (x - grid_start) / (grid_end - grid_start)
        # Dynamic impulse peak in the center
        peak = math.exp(-((t - 0.5) ** 2) / 0.03) * (ss * 0.22) * math.sin(t * 18.0)
        baseline = math.sin(t * math.pi) * (ss * 0.04)
        wy = int(mid_y - peak - baseline)
        wave_pts.append((x, wy))

    # Draw waveform glow
    draw.line(wave_pts, fill=(59, 130, 246, 80), width=int(ss * 0.026), joint="curve")
    draw.line(wave_pts, fill=(96, 165, 250, 180), width=int(ss * 0.012), joint="curve")

    # 4. Bold BUY Vector (Emerald Green Ascending) on Left
    buy_tip = (int(ss * 0.32), int(ss * 0.30))
    buy_l = (int(ss * 0.22), int(ss * 0.44))
    buy_r = (int(ss * 0.42), int(ss * 0.44))
    buy_shaft_top = (int(ss * 0.32), int(ss * 0.42))
    buy_shaft_bot = (int(ss * 0.32), int(ss * 0.58))
    
    # Glow for BUY arrow
    draw.polygon([buy_tip, buy_l, buy_r], fill=(16, 185, 129, 230))
    draw.line([buy_shaft_top, buy_shaft_bot], fill=(16, 185, 129, 230), width=int(ss * 0.032))
    draw.ellipse([buy_tip[0] - 12, buy_tip[1] - 12, buy_tip[0] + 12, buy_tip[1] + 12], fill=(255, 255, 255, 255))

    # 5. Bold SELL Vector (Coral Red Descending) on Right
    sell_tip = (int(ss * 0.68), int(ss * 0.72))
    sell_l = (int(ss * 0.58), int(ss * 0.58))
    sell_r = (int(ss * 0.78), int(ss * 0.58))
    sell_shaft_top = (int(ss * 0.68), int(ss * 0.44))
    sell_shaft_bot = (int(ss * 0.68), int(ss * 0.60))

    # Glow for SELL arrow
    draw.polygon([sell_tip, sell_l, sell_r], fill=(239, 68, 68, 230))
    draw.line([sell_shaft_top, sell_shaft_bot], fill=(239, 68, 68, 230), width=int(ss * 0.032))
    draw.ellipse([sell_tip[0] - 12, sell_tip[1] - 12, sell_tip[0] + 12, sell_tip[1] + 12], fill=(255, 255, 255, 255))

    # 6. Center Energy Bolt (Electric Gold / Amber Lightning)
    cx = int(ss * 0.50)
    cy = int(ss * 0.50)
    bolt = [
        (cx + int(ss * 0.03), cy - int(ss * 0.20)),
        (cx - int(ss * 0.10), cy - int(ss * 0.01)),
        (cx - int(ss * 0.02), cy - int(ss * 0.01)),
        (cx - int(ss * 0.06), cy + int(ss * 0.20)),
        (cx + int(ss * 0.10), cy + int(ss * 0.01)),
        (cx + int(ss * 0.02), cy + int(ss * 0.01)),
    ]
    # Bolt outer gold glow
    draw.polygon(bolt, fill=(245, 158, 11, 240))
    # Inner white hot spark
    bolt_inner = [
        (cx + int(ss * 0.02), cy - int(ss * 0.15)),
        (cx - int(ss * 0.06), cy - int(ss * 0.01)),
        (cx - int(ss * 0.01), cy - int(ss * 0.01)),
        (cx - int(ss * 0.03), cy + int(ss * 0.15)),
        (cx + int(ss * 0.06), cy + int(ss * 0.01)),
        (cx + int(ss * 0.01), cy + int(ss * 0.01)),
    ]
    draw.polygon(bolt_inner, fill=(255, 250, 220, 255))

    # Lanczos downsampling for pristine anti-aliasing
    final_img = base.resize((size, size), Image.Resampling.LANCZOS)
    return final_img


def main():
    assets_dir = Path(__file__).parent.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    img = create_entry_strategy_icon(512)
    png_path = assets_dir / "icon.png"
    img.save(png_path, "PNG")
    print(f"Saved PNG icon at: {png_path}")

    ico_path = assets_dir / "icon.ico"
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"Saved multi-res ICO at: {ico_path} with sizes: {sizes}")


if __name__ == "__main__":
    main()
