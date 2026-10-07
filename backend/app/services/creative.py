import os
import uuid
import logging
from urllib.parse import urljoin
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from bidi.algorithm import get_display

from app.config import get_settings
from app.models import ContentItem, Property

logger = logging.getLogger(__name__)
settings = get_settings()

def get_font(name="Heebo-Regular.ttf", size=40):
    font_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts", name)
    if not os.path.exists(font_path):
        logger.warning(f"Font {name} not found at {font_path}, using default.")
        return ImageFont.load_default()
    return ImageFont.truetype(font_path, size)

def wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        length = font.getlength(test_line) if hasattr(font, "getlength") else font.getsize(test_line)[0]
        if length > max_width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(" ".join(current_line))
        
    return lines

def create_gradient(width, height, start_color, end_color):
    base = Image.new('RGBA', (width, height), start_color)
    top = Image.new('RGBA', (width, height), end_color)
    mask = Image.new('L', (width, height))
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / height))] * width)
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

def smart_center_crop(image, target_size):
    target_w, target_h = target_size
    img_w, img_h = image.size
    
    target_ratio = target_w / target_h
    img_ratio = img_w / img_h
    
    if img_ratio > target_ratio:
        # Image is wider
        new_w = int(img_h * target_ratio)
        new_h = img_h
        left = (img_w - new_w) / 2
        top = 0
        right = left + new_w
        bottom = new_h
    else:
        # Image is taller
        new_w = img_w
        new_h = int(img_w / target_ratio)
        left = 0
        top = (img_h - new_h) / 2
        right = new_w
        bottom = top + new_h
        
    img = image.crop((left, top, right, bottom))
    return img.resize(target_size, Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS)

def render_creative(item: ContentItem, prop: Property) -> str:
    # Sizes
    if item.kind == "story":
        size = (1080, 1920)
    else:
        size = (1080, 1350)
        
    bg_image = None
    if prop and prop.images and len(prop.images) > 0:
        img_path = prop.images[0]
        abs_img_path = os.path.join(settings.MEDIA_DIR, img_path.strip('/'))
        if os.path.exists(abs_img_path):
            bg_image = Image.open(abs_img_path)
            bg_image = smart_center_crop(bg_image, size)
            
    if not bg_image:
        # Branded gradient fallback
        bg_image = create_gradient(size[0], size[1], (20, 20, 50, 255), (60, 20, 60, 255))
        
    # Ensure it's RGBA for drawing
    bg_image = bg_image.convert("RGBA")
    
    # Add dark gradient at bottom for text readability
    gradient_height = int(size[1] * 0.4)
    gradient = create_gradient(size[0], gradient_height, (0, 0, 0, 0), (0, 0, 0, 220))
    bg_image.paste(gradient, (0, size[1] - gradient_height), gradient)
    
    draw = ImageDraw.Draw(bg_image)
    
    font_bold = get_font("Heebo-Bold.ttf", 60)
    font_regular = get_font("Heebo-Regular.ttf", 45)
    
    headline = item.caption.split('\n')[0][:100] if item.caption else "חופשה חלומית"
    cta_text = "הזמינו עכשיו"
    
    # Draw Headline
    lines = wrap_text(headline, font_bold, size[0] - 100)
    lines = lines[:2]
    
    y_text = size[1] - 300
    for line in lines:
        display_line = get_display(line)
        length = font_bold.getlength(display_line) if hasattr(font_bold, "getlength") else font_bold.getsize(display_line)[0]
        # Right align
        x_text = size[0] - 50 - length
        draw.text((x_text, y_text), display_line, font=font_bold, fill=(255, 255, 255, 255))
        y_text += 80
        
    # Draw CTA strip
    cta_display = get_display(cta_text)
    cta_w = font_regular.getlength(cta_display) if hasattr(font_regular, "getlength") else font_regular.getsize(cta_display)[0]
    cta_padding = 40
    cta_bg_rect = [size[0] - 50 - cta_w - cta_padding*2, y_text + 20, size[0] - 50, y_text + 100]
    
    try:
        draw.rounded_rectangle(cta_bg_rect, fill=(220, 50, 50, 255), radius=20)
    except AttributeError:
        draw.rectangle(cta_bg_rect, fill=(220, 50, 50, 255))
    
    draw.text((size[0] - 50 - cta_padding - cta_w, y_text + 35), cta_display, font=font_regular, fill=(255, 255, 255, 255))
    
    out_dir = os.path.join(settings.MEDIA_DIR, "processed")
    os.makedirs(out_dir, exist_ok=True)
    
    filename = f"{item.id}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = os.path.join(out_dir, filename)
    
    final_image = bg_image.convert("RGB")
    final_image.save(out_path, format="JPEG", quality=90)
    
    return f"processed/{filename}"
