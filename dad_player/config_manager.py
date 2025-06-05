from kivy.logger import Logger
import os
import json

class ConfigManager:
    def __init__(self, config_file='music_player_config.json'):
        self.config_file = os.path.join(os.path.expanduser("~"), config_file)
        self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {'music_folders': []}

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f)

    def get_music_folders(self):
        return self.config.get('music_folders', [])

    def add_music_folders(self, new_folders):
        current_folders = self.get_music_folders()
        updated_folders = list(set(current_folders + [f for f in new_folders if os.path.isdir(f)]))
        self.config['music_folders'] = updated_folders
        self.save_config()

    def remove_music_folder(self, folder):
        current_folders = self.get_music_folders()
        if folder in current_folders:
            current_folders.remove(folder)
            self.config['music_folders'] = current_folders
            self.save_config()