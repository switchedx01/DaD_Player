# dad_player/constants.py

APP_NAME = "DaD Player"
APP_VERSION = "3.0.0 BETA Overhaul" # New version for the rewrite

# Default paths (relative to user_data_dir)
DATABASE_NAME = "dad_player_library.sqlite"
SETTINGS_FILE = "dad_player_settings.json"
ART_THUMBNAIL_DIR = "art_thumbnails" # Subdirectory within cache

# Supported audio file extensions
SUPPORTED_AUDIO_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.opus')

# Default image sizes
ALBUM_ART_GRID_SIZE = 200      # For album grid view items
ALBUM_ART_LIST_SIZE = 64       # For song list items (next to song title)
ALBUM_ART_NOW_PLAYING_SIZE = 400 # For the main "Now Playing" display
ALBUM_ART_BLUR_BASE_SIZE = 512 # For generating blurred background

# Placeholder image paths (relative to assets/icons/)
PLACEHOLDER_ALBUM_FILENAME = "placeholder_album.png"
APP_ICON_FILENAME = "dad_player_icon.png"

# Kivy settings panel keys
CONFIG_KEY_MUSIC_FOLDERS = "music_folders"
CONFIG_KEY_AUTOPLAY = "autoplay"
CONFIG_KEY_SHUFFLE = "shuffle"
CONFIG_KEY_REPEAT = "repeat_mode"
CONFIG_KEY_LAST_VOLUME = "last_volume"

# Repeat Modes
REPEAT_NONE = 0
REPEAT_SONG = 1
REPEAT_PLAYLIST = 2
REPEAT_MODES_TEXT = {
    REPEAT_NONE: "Repeat: Off",
    REPEAT_SONG: "Repeat: Song",
    REPEAT_PLAYLIST: "Repeat: All"
}

# Database constants
DB_TRACKS_TABLE = "tracks"
DB_ALBUMS_TABLE = "albums"
DB_ARTISTS_TABLE = "artists"
