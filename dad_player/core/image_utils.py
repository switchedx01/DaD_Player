# dad_player/core/image_utils.py
import io
import os
from kivy.logger import Logger

try:
    from PIL import Image as PILImage, ImageOps, ImageDraw, ImageFont
except ImportError:
    PILImage = None
    ImageOps = None
    ImageDraw = None
    ImageFont = None
    Logger.warning("ImageUtils: Pillow (PIL) not installed. Image resizing and placeholder generation will not work.")

from dad_player.constants import PLACEHOLDER_ALBUM_FILENAME, APP_ICON_FILENAME

def resize_image_data(raw_image_bytes, target_max_dim=512, output_format="PNG", quality=85):
    """
    Resizes raw image bytes to fit within target_max_dim using Pillow,
    maintaining aspect ratio, and returns BytesIO stream in output_format.
    Returns None if Pillow is not available or an error occurs.
    """
    if not PILImage or not ImageOps: # Check if Pillow and ImageOps are available
        Logger.error("ImageUtils: Pillow library (or ImageOps) not available. Cannot resize image.")
        return None

    try:
        pil_image = PILImage.open(io.BytesIO(raw_image_bytes))

        if pil_image.mode not in ('RGB', 'RGBA'):
            if 'A' in pil_image.mode: # Handles modes like LA (Luminance Alpha), PA (Palette Alpha)
                pil_image = pil_image.convert('RGBA')
            else:
                pil_image = pil_image.convert('RGB') # Convert other modes like P, L to RGB
        
        # Use thumbnail to resize while maintaining aspect ratio
        # thumbnail modifies the image in-place
        pil_image.thumbnail((target_max_dim, target_max_dim), PILImage.Resampling.LANCZOS)

        resized_image_bytes_io = io.BytesIO()
        if output_format.upper() == "JPEG" or output_format.upper() == "JPG":
            # Ensure image is RGB for JPEG saving, as JPEG doesn't support alpha
            if pil_image.mode == 'RGBA':
                pil_image = pil_image.convert('RGB')
            pil_image.save(resized_image_bytes_io, format="JPEG", quality=quality, optimize=True)
        else: # Default to PNG
            pil_image.save(resized_image_bytes_io, format="PNG", optimize=True)
        
        resized_image_bytes_io.seek(0)
        Logger.info(f"ImageUtils: Image resized to fit {target_max_dim}x{target_max_dim}. New size: {pil_image.size}, Format: {output_format.upper()}")
        return resized_image_bytes_io
    except Exception as e:
        Logger.error(f"ImageUtils: Error resizing image: {e}")
        return None

def get_placeholder_album_art_path(assets_icons_dir):
    """
    Ensures a placeholder album art image exists and returns its path.
    Creates one if it doesn't exist and Pillow is available.
    """
    if not os.path.isdir(assets_icons_dir):
        Logger.warning(f"ImageUtils: Assets/icons directory not found at {assets_icons_dir}. Cannot get/create placeholder.")
        return None # Or a default known path if you bundle a fallback

    placeholder_path = os.path.join(assets_icons_dir, PLACEHOLDER_ALBUM_FILENAME)
    if os.path.exists(placeholder_path):
        return placeholder_path

    if not PILImage or not ImageDraw or not ImageFont:
        Logger.warning("ImageUtils: Cannot create placeholder album art - Pillow not fully available.")
        return None 

    Logger.info(f"ImageUtils: Placeholder album art not found at {placeholder_path}. Attempting to create.")
    try:
        img_size = 256  # Create a decent sized placeholder
        img = PILImage.new('RGB', (img_size, img_size), color=(50, 50, 60)) # Dark grey
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", img_size // 4)
        except IOError:
            try:
                font = ImageFont.truetype("Roboto-Regular.ttf", img_size // 5)
            except IOError:
                font = ImageFont.load_default() # Absolute fallback
        
        text = "No Art"
        # Calculate text size and position for centering
        if hasattr(draw, 'textbbox'):
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        elif hasattr(draw, 'textsize'):
            text_width, text_height = draw.textsize(text, font=font)
        else:
            text_width, text_height = img_size // 2, img_size // 4
        
        draw.text(
            ((img_size - text_width) / 2, (img_size - text_height) / 2),
            text, fill=(150, 150, 160), font=font
        )
        img.save(placeholder_path)
        Logger.info(f"ImageUtils: Created placeholder album art at: {placeholder_path}")
        return placeholder_path
    except Exception as e:
        Logger.error(f"ImageUtils: Error creating placeholder album art: {e}")
        return None

def get_app_icon_path(assets_icons_dir):
    """
    Ensures an app icon exists and returns its path.
    Creates a basic one if it doesn't exist and Pillow is available.
    """
    if not os.path.isdir(assets_icons_dir):
        Logger.warning(f"ImageUtils: Assets/icons directory not found at {assets_icons_dir}. Cannot get/create app icon.")
        return None

    icon_path = os.path.join(assets_icons_dir, APP_ICON_FILENAME)
    if os.path.exists(icon_path):
        return icon_path

    if not PILImage or not ImageDraw or not ImageFont:
        Logger.warning("ImageUtils: Cannot create app icon - Pillow not fully available.")
        return None

    Logger.info(f"ImageUtils: App icon not found at {icon_path}. Attempting to create.")
    try:
        img_size = 64
        img = PILImage.new('RGB', (img_size, img_size), color=(70, 100, 130)) 
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arialbd.ttf", img_size // 2)
        except IOError:
            try:
                font = ImageFont.truetype("Roboto-Bold.ttf", img_size // 2)
            except IOError:
                font = ImageFont.load_default()
        
        text = "DP" 
        if hasattr(draw, 'textbbox'):
            text_bbox = draw.textbbox((0,0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        else:
            text_width, text_height = draw.textsize(text, font=font)

        draw.text(
            ((img_size - text_width) / 2, (img_size - text_height) / 2 - (img_size // 10) ),
            text, fill=(220, 220, 255), font=font
        )
        img.save(icon_path)
        Logger.info(f"ImageUtils: Created app icon at: {icon_path}")
        return icon_path
    except Exception as e:
        Logger.error(f"ImageUtils: Error creating app icon: {e}")
        return None

