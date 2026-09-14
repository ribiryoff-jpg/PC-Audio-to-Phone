from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (15, 23, 42, 255))
d = ImageDraw.Draw(img)
# green circle
d.ellipse([28, 28, S-28, S-28], fill=(34, 197, 94, 255))
# white sound bars
bars = [(96, 106, 108, 150), (122, 91, 134, 165), (148, 106, 160, 150)]
for x0, y0, x1, y1 in bars:
    d.rounded_rectangle([x0, y0, x1, y1], radius=6, fill=(255, 255, 255, 255))
img.save(r"C:\pc-phone-audio\icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (128, 128), (256, 256)])
print("ICON OK")
