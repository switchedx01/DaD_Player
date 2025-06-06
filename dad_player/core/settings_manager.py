# dad_player/core/settings_manager.py
import os
from kivy.storage.jsonstore import JsonStore
from kivy.logger import Logger
from kivy.app import App

from dad_player.constants import (
    SETTINGS_FILE, CONFIG_KEY_MUSIC_FOLDERS, CONFIG_KEY_AUTOPLAY,
    CONFIG_KEY_SHUFFLE, CONFIG_KEY_REPEAT, REPEAT_NONE, CONFIG_KEY_LAST_VOLUME
)
from dad_player.utils import get_user_data_dir_for_app

class SettingsManager:
    """Handles loading and saving of application settings."""

    def __init__(self):
        self.user_data_dir = get_user_data_dir_for_app()
        self.settings_path = os.path.join(self.user_data_dir, SETTINGS_FILE)
        self.store = JsonStore(self.settings_path)
        self._defaults = {
            CONFIG_KEY_MUSIC_FOLDERS: [],
            CONFIG_KEY_AUTOPLAY: True,
            CONFIG_KEY_SHUFFLE: False,
            CONFIG_KEY_REPEAT: REPEAT_NONE,
            CONFIG_KEY_LAST_VOLUME: 1, #Volume set to 1 due to missing volume controls
        }
        self.last_error = None # Initialize last_error
        self._load_settings()

    def _load_settings(self):
        """Loads settings from the store or applies defaults."""
        for key, default_value in self._defaults.items():
            if not self.store.exists(key):
                self.store.put(key, value=default_value)
                Logger.info(f"SettingsManager: Default value set for '{key}': {default_value}")
            # else:
                # Logger.info(f"SettingsManager: Loaded value for '{key}': {self.store.get(key)['value']}")


    def get(self, key):
        """Gets a setting value."""
        if self.store.exists(key):
            return self.store.get(key)['value']
        elif key in self._defaults:
            Logger.warning(f"SettingsManager: Key '{key}' not found in store, returning default.")
            return self._defaults[key]
        Logger.error(f"SettingsManager: Key '{key}' not found in store or defaults.")
        return None

    def put(self, key, value):
        """Puts a setting value into the store."""
        self.store.put(key, value=value)
        Logger.info(f"SettingsManager: Value for '{key}' saved: {value}")
        # Notify the app if it's running to react to config changes
        app = App.get_running_app()
        if app and hasattr(app, 'on_config_change_custom'):
            app.on_config_change_custom(self, key, value)


    # --- Specific setting accessors/mutators ---

    def get_music_folders(self):
        """Returns a list of music folder paths."""
        return self.get(CONFIG_KEY_MUSIC_FOLDERS) or []

    def add_music_folder(self, folder_path):
        folder_path = os.path.normpath(folder_path)  # Normalize path
        self.last_error = None  # Reset error before attempting to add
        folders = self.get_music_folders()
        Logger.info(f"SettingsManager: Current folders: {folders}")
        Logger.info(f"SettingsManager: Checking if path exists: {folder_path}")
        try:
            if not os.path.isdir(folder_path):
                self.last_error = "Invalid folder path."
                Logger.warning(f"SettingsManager: Invalid folder path not added: {folder_path}")
                return False
        except OSError as e:
            self.last_error = f"Cannot access folder: {str(e)}"
            Logger.warning(f"SettingsManager: Cannot access folder {folder_path}: {e}")
            return False
        if folder_path in folders:
            self.last_error = "Folder already exists."
            Logger.info(f"SettingsManager: Music folder already exists: {folder_path}")
            return False

        folders.append(folder_path)
        self.put(CONFIG_KEY_MUSIC_FOLDERS, sorted(list(set(folders))))
        Logger.info(f"SettingsManager: Added music folder: {folder_path}")
        return True

    def remove_music_folder(self, folder_path):
        """Removes a music folder path."""
        folders = self.get_music_folders()
        if folder_path in folders:
            folders.remove(folder_path)
            self.put(CONFIG_KEY_MUSIC_FOLDERS, sorted(list(set(folders))))
            Logger.info(f"SettingsManager: Removed music folder: {folder_path}")
            return True
        Logger.warning(f"SettingsManager: Music folder not found for removal: {folder_path}")
        return False

    def get_autoplay(self):
        return self.get(CONFIG_KEY_AUTOPLAY)

    def set_autoplay(self, value: bool):
        self.put(CONFIG_KEY_AUTOPLAY, bool(value))

    def get_shuffle(self):
        return self.get(CONFIG_KEY_SHUFFLE)

    def set_shuffle(self, value: bool):
        self.put(CONFIG_KEY_SHUFFLE, bool(value))

    def get_repeat_mode(self):
        return self.get(CONFIG_KEY_REPEAT)

    def set_repeat_mode(self, value: int):
        if value in [REPEAT_NONE, REPEAT_SONG, REPEAT_PLAYLIST]:
            self.put(CONFIG_KEY_REPEAT, int(value))
        else:
            Logger.warning(f"SettingsManager: Invalid repeat mode value: {value}")

    def get_last_volume(self):
        """Gets the last saved volume (0.0 to 1.0)."""
        return float(self.get(CONFIG_KEY_LAST_VOLUME))

    def set_last_volume(self, volume: float):
        """Saves the volume (0.0 to 1.0)."""
        self.put(CONFIG_KEY_LAST_VOLUME, max(0.0, min(1.0, float(volume))))

