"""Expand the existing artwork inside the Windows application icon.

Windows controls the on-screen icon dimensions; this enlarges the symbol itself
within the available 256x256 icon canvas, including smaller sizes.
"""
from pathlib import Path

from PIL import Image


def optimize_icon(source: Path, output: Path) -> None:
    with Image.open(source) as icon_file:
        icon = icon_file.ico.getimage((256, 256)).convert("RGBA")

    alpha = icon.getchannel("A")
    mask = alpha.point(lambda opacity: 255 if opacity > 8 else 0)
    bounds = mask.getbbox()
    if not bounds:
        raise ValueError("The source application icon is entirely transparent")

    content = icon.crop(bounds)
    max_extent = 252  # Keep two pixels of safety margin on each edge.
    scale = min(max_extent / content.width, max_extent / content.height)
    size = (round(content.width * scale), round(content.height * scale))
    resized = content.resize(size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((256 - size[0]) // 2, (256 - size[1]) // 2))

    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(
        output, format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    # Fail the build early if the resulting ICO is invalid or not visibly larger.
    with Image.open(output) as created:
        if (256, 256) not in created.info["sizes"]:
            raise ValueError("The optimized icon is missing its largest size")
        result = created.ico.getimage((256, 256)).convert("RGBA")
    resized_bounds = result.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if resized_bounds is None or (resized_bounds[2] - resized_bounds[0]) <= (bounds[2] - bounds[0]):
        raise ValueError("The optimized artwork has not increased in size")


if __name__ == "__main__":
    directory = Path(__file__).resolve().parent
    optimize_icon(
        directory / "ZaraExImport.ico",
        directory / ".build_assets" / "ZaraExImport.ico",
    )
