# dad_player/utils.py
import os
import sys # Needed for get_user_data_dir_for_app
import hashlib # Needed for generate_file_hash
import re # Needed for sanitize_filename_for_cache

from kivy.logger import Logger
from kivy.metrics import sp, dp
from kivy.core.window import Window # Import Window

# --- Constants for spx fallback ---
DEFAULT_DENSITY_FALLBACK = 1.0
SPX_DEBUG_LOGGING = True # Set to False to reduce console noise once resolved

def spx(value_in_pixels):
    global SPX_DEBUG_LOGGING
    try:
        # Check if Window exists and has the density attribute
        if Window and hasattr(Window, 'density') and Window.density > 0:
            # Using dp() for a general scaling based on density.
            # If this value was specifically for font sizes, Kivy's sp() is usually preferred.
            scaled_value = value_in_pixels * (DEFAULT_DENSITY_FALLBACK / Window.density) 
            if SPX_DEBUG_LOGGING:
                Logger.trace(f"Utils: spx({value_in_pixels}) -> Kivy dp({value_in_pixels}) approx using density {Window.density} -> {dp(value_in_pixels)}")
            return dp(value_in_pixels) # Prefer Kivy's dp() for consistency
        else:
            if SPX_DEBUG_LOGGING:
                status = "Window is None" if not Window else "Window.density not available or invalid"
                Logger.warning(f"Utils: spx({value_in_pixels}): {status}. Returning original value as pixels.")
            return value_in_pixels
    except AttributeError as e: # Catch explicit AttributeError for 'density'
        if SPX_DEBUG_LOGGING:
            Logger.error(f"Utils: spx({value_in_pixels}): AttributeError accessing Window.density ('{e}'). Returning original value as pixels.")
        return value_in_pixels
    except Exception as e: # Catch any other unexpected errors
        if SPX_DEBUG_LOGGING:
            Logger.error(f"Utils: spx({value_in_pixels}): Unexpected error '{e}'. Returning original value as pixels.")
        return value_in_pixels

def get_user_data_dir_for_app():
    """
    Returns the user data directory for the application.
    Creates the directory if it doesn't exist.
    """
    app_name = "DadPlayer" 
    try:
        from dad_player.constants import APP_NAME
        app_name = APP_NAME
    except ImportError:
        Logger.warning("Utils: Could not import APP_NAME from constants. Using default 'DadPlayer'.")

    user_data_dir = ""
    if os.name == 'nt':
        user_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), app_name)
    elif os.name == 'posix':
        if sys.platform == 'darwin':
            user_data_dir = os.path.join(os.path.expanduser('~/Library/Application Support'), app_name)
        else:
            user_data_dir = os.path.join(os.path.expanduser('~/.local/share'), app_name)
    else: 
        user_data_dir = os.path.join(os.path.expanduser('~'), '.' + app_name.lower().replace(" ", ""))
    try:
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
            Logger.info(f"Utils: Created user data directory: {user_data_dir}")
    except OSError as e:
        Logger.error(f"Utils: Could not create user data directory {user_data_dir}: {e}")
        user_data_dir = os.path.join(os.path.abspath("."), ".user_data", app_name) # Fallback
        if not os.path.exists(user_data_dir):
             os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir

def format_duration(seconds):
    if seconds is None or not isinstance(seconds, (int, float)) or seconds < 0:
        return "0:00"
    try:
        minutes = int(seconds // 60)
        remaining_seconds = int(seconds % 60)
        return f"{minutes}:{remaining_seconds:02d}"
    except TypeError:
        return "0:00"


def generate_file_hash(filepath, block_size=65536):
    """Generates an MD5 hash for a file."""
    if not os.path.exists(filepath):
        Logger.warning(f"Utils: File not found for hashing: {filepath}")
        return None
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            buf = f.read(block_size)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(block_size)
        return hasher.hexdigest()
    except IOError as e:
        Logger.error(f"Utils: Could not read file for hashing {filepath}: {e}")
        return None
    except Exception as e:
        Logger.error(f"Utils: Unexpected error hashing file {filepath}: {e}")
        return None


def sanitize_filename_for_cache(filename):
    if not filename:
        return "unknown_file"
    sanitized = re.sub(r'[.\\/:*?"<>|]+', '', filename)
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'[-_]+', '_', sanitized)
    sanitized = sanitized.strip('_-')

    max_len = 100
    if len(sanitized) > max_len:
        name, ext = os.path.splitext(sanitized)
        if len(ext) > max_len -1:
            ext = ext[:max_len-1] if max_len > 1 else ""
            name = ""
        else:
            name = name[:max_len - len(ext) -1]
        sanitized = name + ext if not ext or ext.startswith('.') else name + '.' + ext
        sanitized = sanitized.strip('.') # ensure it doesn't end with just a dot if ext was removed
    
    return sanitized if sanitized else "sanitized_empty"

