import sys
from PIL import Image
w, h, out = sys.argv[1], sys.argv[2], sys.argv[3]
ims = [Image.open(f"shots/{w}x{h}_p{k}.png").convert("RGB") for k in range(9)]
tw = 360 if int(w) < int(h) else 576
th = round(tw * int(h) / int(w))
cols = 5 if int(w) < int(h) else 3
rows = (9 + cols - 1) // cols
sheet = Image.new("RGB", (cols * (tw + 8), rows * (th + 8)), (255, 0, 255))
for k, im in enumerate(ims):
    sheet.paste(im.resize((tw, th), Image.LANCZOS), ((k % cols) * (tw + 8), (k // cols) * (th + 8)))
sheet.save(out)
