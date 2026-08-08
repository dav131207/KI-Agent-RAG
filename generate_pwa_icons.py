import sys
from PIL import Image

def resize_image(input_path, output_path, size):
    try:
        with Image.open(input_path) as img:
            img = img.resize(size, Image.Resampling.LANCZOS)
            img.save(output_path, "PNG")
        print(f"Successfully saved {output_path}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    input_path = "frontend/public/logo.png"
    resize_image(input_path, "frontend/public/pwa-192x192.png", (192, 192))
    resize_image(input_path, "frontend/public/pwa-512x512.png", (512, 512))
    # Apple touch icon
    resize_image(input_path, "frontend/public/apple-touch-icon.png", (180, 180))
