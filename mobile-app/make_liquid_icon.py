import math, os, re
from PIL import Image, ImageDraw, ImageFilter

RES_DIR = os.path.join("android", "app", "src", "main", "res")

def make_droplet_mask(size, scale=1.0, y_shift=0.0):
    mask = Image.new("L", (size, size), 0)
    px = mask.load()
    cx = size * 0.5
    cy = size * (0.55 + y_shift)
    r = size * 0.255 * scale
    tip_y = cy - r * 1.92
    for y in range(size):
        dy = y - cy
        if y < tip_y - 2 or dy > r + 2:
            continue
        for x in range(size):
            dx = x - cx
            if dy >= 0:
                dist = math.hypot(dx, dy) - r
            else:
                t = max(0.0, min(1.0, (y - tip_y) / (cy - tip_y)))
                # Smooth teardrop profile (Apple-like continuous curvature)
                half_w = r * (math.sin(t * math.pi * 0.5) ** 1.18) * (0.28 + 0.72 * t)
                if t > 0.72:
                    # Blend smoothly into lower circle
                    blend = (t - 0.72) / 0.28
                    circ_w = math.sqrt(max(0.0, r * r - dy * dy))
                    half_w = half_w * (1.0 - blend) + circ_w * blend
                dist = abs(dx) - half_w
            if dist <= -1.0:
                px[x, y] = 255
            elif dist < 1.0:
                px[x, y] = int(max(0, min(255, (1.0 - dist) * 127.5)))
    return mask.filter(ImageFilter.GaussianBlur(radius=size * 0.0018))

def make_liquid_droplet(size, scale=1.0):
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = make_droplet_mask(size, scale=scale)

    # Iridescent Apple Liquid Glass gradient fill (aqua -> sky -> cobalt -> pearl-violet)
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gpx = grad.load()
    for y in range(size):
        ny = y / float(size)
        for x in range(size):
            nx = x / float(size)
            # Diagonal liquid glass color blend
            t = max(0.0, min(1.0, 0.55 * nx + 0.65 * ny - 0.12))
            if t < 0.35:
                k = t / 0.35
                r = int(165 * (1 - k) + 56 * k)
                g = int(248 * (1 - k) + 198 * k)
                b = int(255 * (1 - k) + 252 * k)
            elif t < 0.70:
                k = (t - 0.35) / 0.35
                r = int(56 * (1 - k) + 96 * k)
                g = int(198 * (1 - k) + 138 * k)
                b = int(252 * (1 - k) + 255 * k)
            else:
                k = (t - 0.70) / 0.30
                r = int(96 * (1 - k) + 216 * k)
                g = int(138 * (1 - k) + 146 * k)
                b = int(255 * (1 - k) + 255 * k)
            gpx[x, y] = (r, g, b, 242)

    # Soft cyan/blue ambient aura behind droplet
    glow = Image.new("RGBA", (size, size), (56, 189, 248, 0))
    glow_fill = Image.new("RGBA", (size, size), (56, 189, 248, 95))
    glow.paste(glow_fill, (0, 0), mask)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.045))
    layer = Image.alpha_composite(layer, glow)

    # Composite liquid gradient through droplet mask
    drop = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    drop.paste(grad, (0, 0), mask)

    # Inner dark refraction depth near bottom-center for realistic glass volume
    inner_depth = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    idraw = ImageDraw.Draw(inner_depth)
    cx, cy = size * 0.50, size * 0.57
    rr = size * 0.19 * scale
    idraw.ellipse([cx - rr, cy - rr * 0.85, cx + rr, cy + rr * 1.05], fill=(10, 35, 92, 90))
    inner_depth = inner_depth.filter(ImageFilter.GaussianBlur(radius=size * 0.045))
    clipped_depth = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    clipped_depth.paste(inner_depth, (0, 0), mask)
    drop = Image.alpha_composite(drop, clipped_depth)

    # Specular liquid-glass highlight arc (upper-left refraction)
    spec = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(spec)
    sdraw.ellipse(
        [size * 0.34, size * 0.33, size * 0.54, size * 0.62],
        fill=(255, 255, 255, 135)
    )
    sdraw.ellipse(
        [size * 0.40, size * 0.36, size * 0.58, size * 0.65],
        fill=(0, 0, 0, 0)
    )
    # Bright crisp water-drop sparkle dot
    sdraw.ellipse(
        [size * 0.405, size * 0.43, size * 0.455, size * 0.505],
        fill=(255, 255, 255, 225)
    )
    # Bottom-right caustics bounce reflection
    sdraw.ellipse(
        [size * 0.46, size * 0.64, size * 0.66, size * 0.74],
        fill=(186, 242, 255, 120)
    )
    spec = spec.filter(ImageFilter.GaussianBlur(radius=size * 0.014))
    clipped_spec = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    clipped_spec.paste(spec, (0, 0), mask)
    drop = Image.alpha_composite(drop, clipped_spec)

    # Crisp glass rim highlight (difference between mask and slightly eroded mask)
    inner_mask = make_droplet_mask(size, scale=scale * 0.945, y_shift=0.004)
    rim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    r_px = rim.load()
    m_px = mask.load()
    im_px = inner_mask.load()
    for y in range(size):
        for x in range(size):
            diff = max(0, m_px[x, y] - im_px[x, y])
            if diff > 0:
                a = int(min(255, diff * 0.85))
                r_px[x, y] = (235, 248, 255, a)
    rim = rim.filter(ImageFilter.GaussianBlur(radius=size * 0.003))
    drop = Image.alpha_composite(drop, rim)

    layer = Image.alpha_composite(layer, drop)
    return layer

def make_obsidian_bg(size):
    img = Image.new("RGBA", (size, size), (16, 18, 22, 255))
    px = img.load()
    cx, cy = size * 0.5, size * 0.28
    max_d = size * 0.85
    for y in range(size):
        for x in range(size):
            d = math.hypot(x - cx, y - cy) / max_d
            t = max(0.0, min(1.0, d))
            # Apple dark obsidian liquid glass surface
            r = int(34 * (1 - t) + 12 * t)
            g = int(40 * (1 - t) + 15 * t)
            b = int(50 * (1 - t) + 21 * t)
            px[x, y] = (r, g, b, 255)
    # Subtle top glass reflection sheen
    sheen = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sheen)
    sd.ellipse([-size * 0.15, -size * 0.35, size * 1.15, size * 0.45], fill=(255, 255, 255, 22))
    sheen = sheen.filter(ImageFilter.GaussianBlur(radius=size * 0.06))
    return Image.alpha_composite(img, sheen)

def make_full_icon(size, round_clip=False):
    bg = make_obsidian_bg(size)
    fg = make_liquid_droplet(size, scale=1.08)
    out = Image.alpha_composite(bg, fg)
    if round_clip:
        m = Image.new("L", (size, size), 0)
        ImageDraw.Draw(m).ellipse([0, 0, size - 1, size - 1], fill=255)
        res = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        res.paste(out, (0, 0), m)
        return res
    return out

def make_splash_image(w, h):
    canvas = Image.new("RGBA", (w, h), (6, 17, 36, 255))
    # Subtle radial ambient glow in center
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    s = min(w, h)
    r = int(s * 0.34)
    gd.ellipse([w // 2 - r, h // 2 - r, w // 2 + r, h // 2 + r], fill=(24, 96, 168, 55))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=s * 0.12))
    canvas = Image.alpha_composite(canvas, glow)

    # Centered Apple Liquid Glass squircle badge
    badge_s = int(s * 0.28)
    badge = make_full_icon(badge_s, round_clip=False)
    rr = int(badge_s * 0.24)
    rmask = Image.new("L", (badge_s, badge_s), 0)
    ImageDraw.Draw(rmask).rounded_rectangle([0, 0, badge_s - 1, badge_s - 1], radius=rr, fill=255)
    squircle = Image.new("RGBA", (badge_s, badge_s), (0, 0, 0, 0))
    squircle.paste(badge, (0, 0), rmask)
    # Specular glass border on squircle
    bdraw = ImageDraw.Draw(squircle)
    bdraw.rounded_rectangle([1, 1, badge_s - 2, badge_s - 2], radius=rr, outline=(186, 230, 253, 130), width=max(2, badge_s // 90))

    canvas.paste(squircle, ((w - badge_s) // 2, (h - badge_s) // 2), squircle)
    return canvas.convert("RGB")

print("Rendering 512px Liquid Glass master icons...")
master_full = make_full_icon(512, round_clip=False)
master_round = make_full_icon(512, round_clip=True)
master_fg = make_liquid_droplet(512, scale=0.80)  # Safe-zone centered for Android adaptive icons

if os.path.isdir(RES_DIR):
    updated = 0
    for root, dirs, files in os.walk(RES_DIR):
        folder = os.path.basename(root)
        for fn in files:
            path = os.path.join(root, fn)
            low = fn.lower()
            if folder.startswith("mipmap-") and low.endswith(".png"):
                try:
                    with Image.open(path) as im:
                        sz = im.size
                except Exception:
                    sz = (192, 192)
                if "foreground" in low:
                    master_fg.resize(sz, Image.LANCZOS).save(path, "PNG")
                    updated += 1
                elif "round" in low:
                    master_round.resize(sz, Image.LANCZOS).save(path, "PNG")
                    updated += 1
                elif "ic_launcher" in low:
                    master_full.resize(sz, Image.LANCZOS).save(path, "PNG")
                    updated += 1
            elif folder.startswith("drawable") and low == "splash.png":
                try:
                    with Image.open(path) as im:
                        w, h = im.size
                except Exception:
                    w, h = (1080, 1920)
                make_splash_image(w, h).save(path, "PNG")
                updated += 1

    # Update adaptive icon background color to Apple dark obsidian (#14171D)
    bg_color_xml = os.path.join(RES_DIR, "values", "ic_launcher_background.xml")
    if os.path.exists(bg_color_xml):
        txt = open(bg_color_xml, "r", encoding="utf-8").read()
        txt = re.sub(r'(<color\s+name="ic_launcher_background"\s*>)[^<]+(</color>)', r'\g<1>#14171D\g<2>', txt)
        open(bg_color_xml, "w", encoding="utf-8").write(txt)

    # Update drawable/ic_launcher_background.xml if present (gradient dark obsidian glass)
    for dsub in ["drawable", "drawable-v24"]:
        bg_draw = os.path.join(RES_DIR, dsub, "ic_launcher_background.xml")
        if os.path.exists(bg_draw):
            with open(bg_draw, "w", encoding="utf-8") as f:
                f.write(
                    '<?xml version="1.0" encoding="utf-8"?>\n'
                    '<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">\n'
                    '  <gradient android:type="radial" android:gradientRadius="85%p" android:centerX="50%" android:centerY="28%" android:startColor="#242B37" android:endColor="#0D1016"/>\n'
                    '</shape>\n'
                )

    # Update Android 12+ Splash background color in styles.xml if present
    styles_xml = os.path.join(RES_DIR, "values", "styles.xml")
    if os.path.exists(styles_xml):
        stxt = open(styles_xml, "r", encoding="utf-8").read()
        stxt = re.sub(r'(<item\s+name="android:windowSplashScreenBackground"\s*>)[^<]+(</item>)', r'\g<1>#061124\g<2>', stxt)
        open(styles_xml, "w", encoding="utf-8").write(stxt)

    print(f"Updated {updated} Android Liquid Glass icon & splash assets!")
else:
    print("Warning: android/app/src/main/res not found.")
