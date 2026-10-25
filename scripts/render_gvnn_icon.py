"""Render the GVNN app icon as an antialiased PNG (requires Pillow).

Usage: python render_gvnn_icon.py /path/to/static/description/icon.png
Vector source: custom-addons/edu_gvnn/static/description/icon.svg.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def render(destination):
    scale = 4
    size = 128 * scale
    image = Image.new('RGBA', (size, size))
    pixels = image.load()
    start, end = (23, 106, 198), (19, 168, 158)
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            pixels[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(start, end)) + (255,)
    mask = Image.new('L', (size, size))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=28 * scale, fill=255)
    image.putalpha(mask)
    draw = ImageDraw.Draw(image)

    def points(values):
        return [(round(x * scale), round(y * scale)) for x, y in values]

    def bezier(p0, p1, p2, p3):
        result = []
        for i in range(33):
            t = i / 32
            result.append(tuple((1-t)**3*a + 3*(1-t)**2*t*b + 3*(1-t)*t*t*c + t**3*d
                                for a, b, c, d in zip(p0, p1, p2, p3)))
        return result

    draw.polygon(points([(64, 23), (107, 44), (64, 65), (21, 44)]), fill='white')
    band = [(39, 55), (39, 70)] + bezier((39, 70), (52, 82), (76, 82), (89, 70)) + [(89, 55)]
    draw.line(points(band), fill='white', width=5*scale, joint='curve')
    draw.line(points([(104, 47), (104, 72)]), fill='white', width=5*scale)
    draw.ellipse((100*scale, 73*scale, 108*scale, 81*scale), fill='#f5cc68')
    book = bezier((30,83),(42,80),(53,82),(64,89))
    book += bezier((64,89),(75,82),(86,80),(98,83))
    book += [(98,104)] + bezier((98,104),(86,101),(75,103),(64,109))
    book += bezier((64,109),(53,103),(42,101),(30,104))
    draw.polygon(points(book), fill='white')
    draw.line(points([(64,90),(64,107)]), fill='#158ba9', width=3*scale)
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    image.resize((128,128), getattr(Image, 'Resampling', Image).LANCZOS).save(destination)


if __name__ == '__main__':
    render(sys.argv[1])
