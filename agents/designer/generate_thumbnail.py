"""
フィギュアサムネイル自動生成スクリプト
Usage:
  python generate_thumbnail.py --zip 14041.zip --size 28 --output 14041_thumb.webp
  python generate_thumbnail.py --zip 14041.zip --size 28 --bg existing_bg.jpg  # 既存背景を再利用
"""
import argparse
import io
import os
import sys
import zipfile

import replicate
import requests
from PIL import Image, ImageDraw, ImageFont

# ── 設定 ──────────────────────────────────────────
BG_CACHE_DIR  = os.path.expanduser("~/thumbnail_backgrounds")
TOKEN_FILE    = os.path.expanduser("~/.replicate_token")
CANVAS_SIZE   = 1200
FONT_BOLD     = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# キャラ世界観 → 背景プロンプトのマッピング（商品名/タグで切り替え可能）
BG_PROMPTS = {
    "japanese": (
        "miniature diorama world, tiny Japanese castle on a stone platform, "
        "tilt-shift macro photography, selective focus blur, "
        "warm golden hour lighting, hand-painted miniature scenery, "
        "tabletop RPG diorama style, soft bokeh background, "
        "no people, no figures, just background scene, "
        "dramatic sky with clouds, stone floor tiles"
    ),
    "fantasy": (
        "miniature diorama fantasy world, tiny dragon's lair on rocky terrain, "
        "tilt-shift macro photography, magical glowing crystals, "
        "mysterious blue lighting, hand-painted miniature scenery, "
        "tabletop RPG diorama style, soft bokeh background, "
        "no people, no figures, just background scene"
    ),
    "scifi": (
        "miniature diorama sci-fi world, tiny futuristic city on a metal platform, "
        "tilt-shift macro photography, neon lights, "
        "cool blue lighting, hand-painted miniature scenery, "
        "cyberpunk diorama style, soft bokeh background, "
        "no people, no figures, just background scene"
    ),
    "default": (
        "miniature diorama world, tiny scenic landscape on a platform, "
        "tilt-shift macro photography, selective focus blur, "
        "warm golden hour lighting, hand-painted miniature scenery, "
        "tabletop RPG diorama style, soft bokeh background, "
        "no people, no figures, just background scene"
    ),
}


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return os.environ.get("REPLICATE_API_TOKEN", "")


def generate_background(style: str = "japanese", cache_key: str = "") -> Image.Image:
    """AI背景を生成（キャッシュあれば再利用）"""
    os.makedirs(BG_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(BG_CACHE_DIR, f"bg_{style}_{cache_key}.jpg") if cache_key \
                 else os.path.join(BG_CACHE_DIR, f"bg_{style}.jpg")

    if os.path.exists(cache_path):
        print(f"  背景キャッシュ使用: {cache_path}")
        return Image.open(cache_path).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)

    print(f"  背景生成中（FLUX 1.1 Pro / {style}）...")
    token = load_token()
    os.environ["REPLICATE_API_TOKEN"] = token

    prompt = BG_PROMPTS.get(style, BG_PROMPTS["default"])
    output = replicate.run(
        "black-forest-labs/flux-1.1-pro",
        input={
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "output_format": "jpg",
            "output_quality": 90,
            "safety_tolerance": 2,
        },
    )
    resp = requests.get(str(output))
    with open(cache_path, "wb") as f:
        f.write(resp.content)
    print(f"  背景保存: {cache_path}")
    return Image.open(io.BytesIO(resp.content)).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)


def load_figures_from_zip(zip_path: str):
    """ZIPから_01と_03の画像を取得（バウンディングボックス付き）"""
    product_id = os.path.splitext(os.path.basename(zip_path))[0]
    with zipfile.ZipFile(zip_path) as z:
        names = [f.filename for f in z.infolist()]

        def load(suffix):
            candidates = [n for n in names if n.endswith(f"_{suffix}.png") or n.endswith(f"_0{suffix}.png")]
            # _01, _03 優先。なければ _02
            for c in candidates:
                with z.open(c) as f:
                    img = Image.open(io.BytesIO(f.read()))
                    img.load()
                    return img.convert("RGBA")
            return None

        img_full   = load("1") or load("01")
        img_detail = load("3") or load("03") or img_full

    def get_bbox(img):
        return img.split()[3].getbbox()

    return img_full, img_detail, get_bbox(img_full), get_bbox(img_detail)


def draw_size_badge(draw: ImageDraw.Draw, size_cm: int):
    """右端にサイズバッジを描画"""
    badge_cx  = CANVAS_SIZE - 52
    badge_top = int(CANVAS_SIZE * 0.13)
    badge_bot = int(CANVAS_SIZE * 0.87)

    for y in range(badge_top + 42, badge_bot - 42, 12):
        draw.ellipse([badge_cx-3, y-3, badge_cx+3, y+3], fill=(255, 255, 255, 200))
    for cy in [badge_top, badge_bot]:
        draw.ellipse([badge_cx-9, cy-9, badge_cx+9, cy+9], fill=(255, 255, 255, 255))

    mid_y = (badge_top + badge_bot) // 2
    bw, bh = 84, 70
    draw.rounded_rectangle(
        [badge_cx-bw//2, mid_y-bh//2, badge_cx+bw//2, mid_y+bh//2],
        radius=20, fill=(18, 18, 55, 240))
    draw.rounded_rectangle(
        [badge_cx-bw//2, mid_y-bh//2, badge_cx+bw//2, mid_y+bh//2],
        radius=20, outline=(180, 180, 255, 150), width=2)

    try:
        fb = ImageFont.truetype(FONT_BOLD, 31)
        fs = ImageFont.truetype(FONT_BOLD, 16)
    except OSError:
        fb = fs = ImageFont.load_default()

    draw.text((badge_cx, mid_y - 13), str(size_cm), font=fb, fill=(255,255,255,255), anchor="mm")
    draw.text((badge_cx, mid_y + 17), "cm",         font=fs, fill=(210,210,255,200), anchor="mm")


def create_thumbnail(
    zip_path: str,
    size_cm: int,
    output_path: str,
    bg_style: str = "japanese",
    bg_image_path: str = "",
) -> str:
    print(f"\n[{os.path.basename(zip_path)}] サムネイル生成開始")

    # 背景
    if bg_image_path and os.path.exists(bg_image_path):
        print(f"  指定背景使用: {bg_image_path}")
        bg = Image.open(bg_image_path).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)
    else:
        product_id = os.path.splitext(os.path.basename(zip_path))[0]
        bg = generate_background(bg_style, cache_key=product_id)

    canvas = bg.copy()

    # フィギュア読み込み
    img_full, img_detail, bb_full, bb_detail = load_figures_from_zip(zip_path)

    # 右：全身
    fig_full = img_full.crop(bb_full)
    rh = int(CANVAS_SIZE * 0.93)
    rw = int(fig_full.width * rh / fig_full.height)
    fig_full_r = fig_full.resize((rw, rh), Image.LANCZOS)
    rx = 520 + (540 - rw) // 2
    canvas.paste(fig_full_r, (rx, int(CANVAS_SIZE * 0.035)), mask=fig_full_r.split()[3])

    # 左：上半身クローズアップ（上52%）
    cx0, cy0, cx1, cy1 = bb_detail
    crop_bottom = cy0 + int((cy1 - cy0) * 0.52)
    fig_detail_c = img_detail.crop((cx0, cy0, cx1, crop_bottom))
    lh = int(CANVAS_SIZE * 0.92)
    lw = int(fig_detail_c.width * lh / fig_detail_c.height)
    fig_detail_r = fig_detail_c.resize((lw, lh), Image.LANCZOS)
    canvas.paste(fig_detail_r, (-int(lw * 0.08), int(CANVAS_SIZE * 0.04)), mask=fig_detail_r.split()[3])

    # サイズバッジ
    draw_size_badge(ImageDraw.Draw(canvas), size_cm)

    # 保存
    canvas.convert("RGB").save(output_path, "WEBP", quality=90)
    size_kb = os.path.getsize(output_path) // 1024
    print(f"  完成: {output_path} ({size_kb}KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="フィギュアサムネイル自動生成")
    parser.add_argument("--zip",    required=True,  help="商品ZIPファイルのパス")
    parser.add_argument("--size",   type=int, default=28, help="商品サイズ（cm）")
    parser.add_argument("--output", default="",     help="出力WebPパス（省略時: 入力と同フォルダ）")
    parser.add_argument("--style",  default="japanese",
                        choices=list(BG_PROMPTS.keys()), help="背景スタイル")
    parser.add_argument("--bg",     default="",     help="既存背景画像パス（指定時はAI生成をスキップ）")
    args = parser.parse_args()

    out = args.output or os.path.splitext(args.zip)[0] + "_thumb.webp"
    create_thumbnail(args.zip, args.size, out, args.style, args.bg)


if __name__ == "__main__":
    main()
