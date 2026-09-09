from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "website" / "group-photo" / "work" / "identity-sheet.png"

CHARACTERS = [
    ("FUFU-enfp", "FUFU"),
    ("haide-entp", "haide"),
    ("Mimi-enfj", "Mimi"),
    ("艾莎-intj", "艾莎"),
    ("陆姚-entj", "陆姚"),
    ("软软-infp", "软软"),
    ("牧师-enfj", "牧师"),
    ("whiskle-infp", "whiskle"),
    ("lukos-infj", "lukos"),
    ("点儿-intp", "点儿"),
    ("Liiie-infj", "Liiie"),
    ("QC-entp", "QC"),
]


def main() -> None:
    width, height = 2048, 1536
    columns, rows = 4, 3
    cell_width, cell_height = width // columns, height // rows
    sheet = Image.new("RGB", (width, height), (245, 240, 235))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 34)

    for index, (folder, label) in enumerate(CHARACTERS):
        source = ROOT / "character reference" / folder / f"{folder}.png"
        portrait = Image.open(source).convert("RGB")
        portrait.thumbnail((cell_width - 24, cell_height - 58), Image.Resampling.LANCZOS)

        column, row = index % columns, index // columns
        left, top = column * cell_width, row * cell_height
        x = left + (cell_width - portrait.width) // 2
        y = top + 48 + (cell_height - 58 - portrait.height) // 2
        sheet.paste(portrait, (x, y))
        draw.rectangle(
            (left, top, left + cell_width - 1, top + cell_height - 1),
            outline=(120, 105, 95),
            width=3,
        )
        draw.text((left + 14, top + 8), f"{index + 1}. {label}", fill=(55, 45, 40), font=font)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
