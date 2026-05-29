"""
フィギュアサムネイル自動生成スクリプト
Usage:
  python generate_thumbnail.py --zip 14041.zip --size 28
  python generate_thumbnail.py --zip 14041.zip --size 28 --bg existing_bg.jpg
  python generate_thumbnail.py --zip 14045.zip --size 15 --layout single --style pirate_town
"""
import argparse
import io
import os
import zipfile

import replicate
import requests
from PIL import Image, ImageDraw, ImageFont

# ── 設定 ──────────────────────────────────────────────────────────────
BG_CACHE_DIR = os.path.expanduser("~/thumbnail_backgrounds")
TOKEN_FILE   = os.path.expanduser("~/.replicate_token")
CANVAS_SIZE  = 1200
FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ── 背景スタイル（学習データ12枚から抽出したルール） ──────────────────
BG_PROMPTS = {
    # 海賊・冒険系（One Piece等）
    "pirate":       ("cinematic background, pirate ship wooden deck at sunset, dramatic purple orange sky, "
                     "golden bokeh light particles, ship rigging, realistic photography style, "
                     "no people, no figures, just background"),
    # バトル・歴史・武将（Kingdom等）
    "castle":       ("cinematic background, ancient castle fortress battlements, dramatic purple sunset sky, "
                     "stone tiles floor, dark brooding atmosphere, "
                     "no people, no figures, just background"),
    # 宇宙・バトル（Dragon Ball等）
    "space":        ("cinematic background, deep space galaxy with purple nebula and glowing stars, "
                     "distant planet, cosmic energy, dramatic lighting, "
                     "no people, no figures, just background"),
    # 和風・学校・桜
    "shrine":       ("cinematic background, Japanese torii gate shrine with cherry blossom sakura petals, "
                     "warm sunset glow, stone path, traditional lanterns, "
                     "no people, no figures, just background"),
    # ダーク・忍・悪役（Naruto暁等）
    "dark_ninja":   ("cinematic background, dark mystical scene, red blood moon with Sharingan eye symbol, "
                     "purple magical mist, flying crows, Japanese kanji glowing red, dark atmospheric, "
                     "no people, no figures, just background"),
    # 和の道場・忍（明るい系）
    "dojo":         ("cinematic background, traditional Japanese dojo interior, tatami floor, "
                     "shoji paper screens with soft light, wooden beams, garden outside window, "
                     "no people, no figures, just background"),
    # VTuber・現代・夜の街
    "night_city":   ("cinematic background, beautiful night city street with glowing street lamps, "
                     "wet cobblestone reflecting lights, purple starry sky, bokeh city lights, "
                     "no people, no figures, just background"),
    # チビ・可愛い（One Pieceルフィ等）
    "pirate_town":  ("cinematic background, bright cheerful pirate town village, blue sky white clouds, "
                     "colorful buildings, pirate flag, warm sunlight, welcoming atmosphere, "
                     "no people, no figures, just background"),
    # 神秘・妖怪・和風（犬夜叉等）
    "mystic":       ("cinematic background, mystical night forest under crescent moon, "
                     "purple magical energy lightning, glowing ancient trees, ethereal atmosphere, "
                     "no people, no figures, just background"),
    # 廃墟・アポカリプス
    "ruins":        ("cinematic background, urban ruins and destroyed buildings, dramatic god rays light, "
                     "overcast sky, debris and rubble, intense atmospheric, "
                     "no people, no figures, just background"),
    # 港・夕暮れ・オシャレ
    "harbor":       ("cinematic background, beautiful harbor at golden hour sunset, lighthouse, "
                     "wooden pier, glowing bokeh lights, warm orange pink sky reflection on water, "
                     "no people, no figures, just background"),
    # ビーチ・夏
    "beach":        ("cinematic background, sunny tropical beach, colorful beach umbrella, "
                     "clear turquoise ocean, bright blue sky white clouds, palm trees, "
                     "no people, no figures, just background"),
    # サンリオ・可愛い・ピンク（マイメロ等）
    "kawaii_pink":  ("dreamy background, soft pink bokeh with floating hearts and rose petals, "
                     "pearl necklace, heart-shaped mirror, lace, sparkles, "
                     "no people, no figures, just background"),
    # サンリオ・ダーク・紫（クロミ等）
    "kawaii_purple":("dreamy background, deep purple bokeh with floating hearts and crystals, "
                     "gothic lace, purple gem stones, sparkles, mysterious cute atmosphere, "
                     "no people, no figures, just background"),
    # VTuber・ステージ（ぬいぐるみ）
    "stage_light":  ("dreamy background, idol concert stage with purple and lavender spotlights, "
                     "geometric light patterns, soft bokeh circles, glowing floor, "
                     "no people, no figures, just background"),
    # テクノロジー・SF（ベイマックス等）
    "tech_blue":    ("cinematic background, deep blue technology circuit board pattern, "
                     "glowing blue neon lines, digital grid, sci-fi atmosphere, "
                     "no people, no figures, just background"),
    # 洞窟・クリスタル（モンスター等）
    "crystal_cave": ("cinematic background, dark mystical cave with glowing blue crystal formations, "
                     "stalactites, magical blue light, stone floor, "
                     "no people, no figures, just background"),
    # レインボー・パステル（大型ぬいぐるみ）
    "rainbow_pastel":("dreamy background, rainbow gradient pastel colors, glowing stars and sparkles, "
                      "soft bokeh light orbs, magical cheerful atmosphere, "
                      "no people, no figures, just background"),
    # ポケモン・自然フィールド
    "pokemon_field":("cinematic background, bright sunny day, lush green grass field, "
                     "fluffy white clouds, blue sky, soft bokeh nature, "
                     "no people, no figures, just background"),
    # グッズ・速度感（バッグ等）
    "speed_lines":  ("cinematic background, dynamic blue speed lines radiating energy, "
                     "glowing streaks, high-speed motion blur effect, cool blue tones, "
                     "no people, no figures, just background"),
    # トロピカル・ジャングル・夏
    "tropical_jungle":("cinematic background, tropical jungle beach with banana trees, "
                       "bright yellow bananas, tropical flowers, warm sunny atmosphere, "
                       "no people, no figures, just background"),
    # 汎用デフォルト
    "default":      ("cinematic background, dramatic fantasy landscape with atmospheric lighting, "
                     "bokeh depth of field, vivid colors, "
                     "no people, no figures, just background"),
}


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return os.environ.get("REPLICATE_API_TOKEN", "")


def generate_background(style: str = "default", cache_key: str = "") -> Image.Image:
    """AI背景を生成（キャッシュあれば再利用）"""
    os.makedirs(BG_CACHE_DIR, exist_ok=True)
    fname = f"bg_{style}_{cache_key}.jpg" if cache_key else f"bg_{style}.jpg"
    cache_path = os.path.join(BG_CACHE_DIR, fname)

    if os.path.exists(cache_path):
        print(f"  背景キャッシュ使用: {cache_path}")
        return Image.open(cache_path).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)

    print(f"  背景生成中（FLUX 1.1 Pro / {style}）...")
    os.environ["REPLICATE_API_TOKEN"] = load_token()
    prompt = BG_PROMPTS.get(style, BG_PROMPTS["default"])
    output = replicate.run(
        "black-forest-labs/flux-1.1-pro",
        input={"prompt": prompt, "aspect_ratio": "1:1",
               "output_format": "jpg", "output_quality": 90, "safety_tolerance": 2},
    )
    resp = requests.get(str(output))
    with open(cache_path, "wb") as f:
        f.write(resp.content)
    print(f"  背景保存: {cache_path}")
    return Image.open(io.BytesIO(resp.content)).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)


def load_figures_from_zip(zip_path: str):
    """ZIPから_01と_03の画像を取得（バウンディングボックス付き）"""
    with zipfile.ZipFile(zip_path) as z:
        names = [f.filename for f in z.infolist()]

        def load(suffixes):
            for s in suffixes:
                cands = [n for n in names if n.lower().endswith(f"_{s}.png")]
                for c in cands:
                    with z.open(c) as f:
                        img = Image.open(io.BytesIO(f.read()))
                        img.load()
                        return img.convert("RGBA")
            return None

        img_full   = load(["01", "1"])
        img_detail = load(["03", "3"]) or img_full

    def bbox(img):
        return img.split()[3].getbbox()

    return img_full, img_detail, bbox(img_full), bbox(img_detail)


def draw_size_badge(draw: ImageDraw.Draw, size_cm: int,
                    fig_top: int, fig_bot: int, fig_right: int,
                    badge_style: str = "filled",
                    line_style: str = "dotted"):
    """サイズバッジを描画（全身フィギュアの頭頂〜足元に合わせる）
    badge_style: filled / outlined / filled_black
    line_style:  dotted / solid
    """
    badge_cx  = min(fig_right + 26, CANVAS_SIZE - 46)
    badge_top = fig_top
    badge_bot = fig_bot

    # ライン
    if line_style == "solid":
        draw.line([badge_cx, badge_top + 14, badge_cx, badge_bot - 14], fill=(0, 0, 0, 220), width=2)
    else:  # dotted
        dot_color = (255, 255, 255, 200) if badge_style != "outlined" else (255, 255, 255, 230)
        for y in range(badge_top + 28, badge_bot - 28, 12):
            draw.ellipse([badge_cx-3, y-3, badge_cx+3, y+3], fill=dot_color)

    # エンドポイント
    ep_color = (0, 0, 0, 230) if line_style == "solid" else (255, 255, 255, 255)
    for cy in [badge_top, badge_bot]:
        draw.ellipse([badge_cx-8, cy-8, badge_cx+8, cy+8], fill=ep_color)

    # バッジ本体
    mid_y = (badge_top + badge_bot) // 2
    bw, bh = 82, 68
    box = [badge_cx-bw//2, mid_y-bh//2, badge_cx+bw//2, mid_y+bh//2]

    if badge_style == "filled_black":
        draw.rounded_rectangle(box, radius=22, fill=(10, 10, 10, 250))
        txt_color = (255, 255, 255, 255)
    elif badge_style == "outlined":
        draw.rounded_rectangle(box, radius=20, fill=(18, 18, 58, 140))
        draw.rounded_rectangle(box, radius=20, outline=(255, 255, 255, 220), width=2)
        txt_color = (255, 255, 255, 255)
    else:  # filled (dark navy)
        draw.rounded_rectangle(box, radius=20, fill=(18, 18, 58, 245))
        draw.rounded_rectangle(box, radius=20, outline=(255, 255, 255, 60), width=1)
        txt_color = (255, 255, 255, 255)

    try:
        fb = ImageFont.truetype(FONT_BOLD, 30)
        fs = ImageFont.truetype(FONT_BOLD, 15)
    except OSError:
        fb = fs = ImageFont.load_default()

    draw.text((badge_cx, mid_y-12), str(size_cm), font=fb, fill=txt_color, anchor="mm")
    draw.text((badge_cx, mid_y+16), "cm",         font=fs, fill=txt_color, anchor="mm")


def create_thumbnail(
    zip_path: str,
    size_cm: int,
    output_path: str,
    bg_style: str = "default",
    bg_image_path: str = "",
    layout: str = "auto",         # "auto" | "double" | "single"
    badge_style: str = "filled",  # "filled" | "outlined" | "filled_black"
    line_style: str = "dotted",   # "dotted" | "solid"
) -> str:
    print(f"\n[{os.path.basename(zip_path)}] サムネイル生成開始 layout={layout}")

    # 背景
    if bg_image_path and os.path.exists(bg_image_path):
        print(f"  指定背景使用: {bg_image_path}")
        bg = Image.open(bg_image_path).convert("RGBA").resize((CANVAS_SIZE, CANVAS_SIZE), Image.LANCZOS)
    else:
        product_id = os.path.splitext(os.path.basename(zip_path))[0]
        bg = generate_background(bg_style, cache_key=product_id)

    canvas = bg.copy()
    img_full, img_detail, bb_full, bb_detail = load_figures_from_zip(zip_path)

    # レイアウト自動判定: フィギュアのアスペクト比で判断
    # 高さ/幅 > 1.8 → スリム → double, それ以下 → チビ → single
    fw = bb_full[2] - bb_full[0]
    fh = bb_full[3] - bb_full[1]
    if layout == "auto":
        layout = "double" if (fh / fw) >= 1.8 else "single"
        print(f"  レイアウト自動判定: h/w={fh/fw:.2f} → {layout}")

    if layout == "double":
        # ── 2ショット: クローズアップ（背面）+ 全身（前面）──
        cx0, cy0, cx1, cy1 = bb_detail
        crop_bottom = cy0 + int((cy1 - cy0) * 0.52)
        fig_det = img_detail.crop((cx0, cy0, cx1, crop_bottom))
        lh = int(CANVAS_SIZE * 1.02)
        lw = int(fig_det.width * lh / fig_det.height)
        canvas.paste(fig_det.resize((lw, lh), Image.LANCZOS),
                     (-int(lw * 0.06), -int(CANVAS_SIZE * 0.01)),
                     mask=fig_det.resize((lw, lh), Image.LANCZOS).split()[3])

        fig_full = img_full.crop(bb_full)
        rh = int(CANVAS_SIZE * 0.90)
        rw = int(fig_full.width * rh / fig_full.height)
        fig_full_r = fig_full.resize((rw, rh), Image.LANCZOS)
        rx = int(CANVAS_SIZE * 0.42) + (int(CANVAS_SIZE * 0.50) - rw) // 2
        ry = int(CANVAS_SIZE * 0.05)
        canvas.paste(fig_full_r, (rx, ry), mask=fig_full_r.split()[3])

    else:
        # ── 1ショット: 全身中央配置 ──
        fig_full = img_full.crop(bb_full)
        scale = (CANVAS_SIZE * 0.95) / fig_full.height
        fw2 = int(fig_full.width * scale)
        fh2 = int(fig_full.height * scale)
        fig_full_r = fig_full.resize((fw2, fh2), Image.LANCZOS)
        rx = (CANVAS_SIZE - fw2) // 2
        ry = int(CANVAS_SIZE * 0.025)
        canvas.paste(fig_full_r, (rx, ry), mask=fig_full_r.split()[3])
        rw = fw2
        rh = fh2

    # サイズバッジ
    draw_size_badge(
        ImageDraw.Draw(canvas), size_cm,
        fig_top=ry, fig_bot=ry + rh, fig_right=rx + rw,
        badge_style=badge_style,
        line_style=line_style,
    )

    canvas.convert("RGB").save(output_path, "WEBP", quality=90)
    print(f"  完成: {output_path} ({os.path.getsize(output_path)//1024}KB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="フィギュアサムネイル自動生成")
    parser.add_argument("--zip",    required=True)
    parser.add_argument("--size",   type=int, default=28,   help="商品サイズ（cm）")
    parser.add_argument("--output", default="",             help="出力パス（省略時: ZIPと同フォルダ）")
    parser.add_argument("--style",  default="default",      choices=list(BG_PROMPTS.keys()))
    parser.add_argument("--bg",     default="",             help="既存背景画像パス")
    parser.add_argument("--layout", default="auto",         choices=["auto","double","single"])
    parser.add_argument("--badge",  default="filled",  choices=["filled","outlined","filled_black"])
    parser.add_argument("--line",   default="dotted",  choices=["dotted","solid"])
    args = parser.parse_args()

    out = args.output or os.path.splitext(args.zip)[0] + "_thumb.webp"
    create_thumbnail(args.zip, args.size, out, args.style, args.bg, args.layout, args.badge, args.line)


if __name__ == "__main__":
    main()
