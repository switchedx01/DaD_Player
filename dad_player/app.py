# dad_player/app.py
from kivy.app import App
from kivy.lang import Builder
from kivy.logger import Logger
import os
import sys
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.uix.popup import Popup # Added for global_scan_progress_update potentially
from kivy.clock import Clock # Added for _initial_library_check potentially

# Core components
from dad_player.core.settings_manager import SettingsManager
from dad_player.core.player_engine import PlayerEngine
from dad_player.core.library_manager import LibraryManager
from dad_player.core.image_utils import get_app_icon_path, get_placeholder_album_art_path

from dad_player.constants import APP_NAME, APP_VERSION, CONFIG_KEY_LAST_VOLUME

class DadPlayerApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs) # This call makes Kivy's self.user_data_dir available
        Logger.info("DadPlayerApp: __init__ started.")
        # Initialize core components here, once.
        self.settings_manager = SettingsManager()
        try:
            self.player_engine = PlayerEngine(settings_manager=self.settings_manager)
            initial_volume_0_1 = self.settings_manager.get_last_volume()
            self.player_engine.set_volume(int(initial_volume_0_1 * 100), dispatch_event=False)
            Logger.info("DadPlayerApp: PlayerEngine initialized.")
        except RuntimeError as e:
            Logger.critical(f"DadPlayerApp: PlayerEngine initialization failed: {e}. Is VLC installed?")
            self.player_engine = None
        except Exception as e:
            Logger.critical(f"DadPlayerApp: Unexpected error during PlayerEngine initialization: {e}")
            self.player_engine = None

        self.library_manager = LibraryManager(settings_manager=self.settings_manager)
        Logger.info("DadPlayerApp: LibraryManager initialized.")
        self.screen_manager = None # Will be set in build()

        # Kivy's self.user_data_dir is now available and set.
        # We don't assign to it. We use it.
        Logger.info(f"DadPlayerApp: Kivy User data directory is: {self.user_data_dir}")

        # Define asset and icon paths
        current_script_path = os.path.dirname(os.path.abspath(__file__))
        self.assets_dir = os.path.join(current_script_path, "..", "assets")
        self.icons_dir = os.path.join(self.assets_dir, "icons")
        Logger.info(f"DadPlayerApp: Assets directory: {self.assets_dir}")
        Logger.info(f"DadPlayerApp: Icons directory: {self.icons_dir}")

        # Use Kivy's self.user_data_dir to construct art_cache_dir
        self.art_cache_dir = os.path.join(self.user_data_dir, "cache", "art_thumbnails")
        if not os.path.exists(self.art_cache_dir):
            os.makedirs(self.art_cache_dir, exist_ok=True) # Ensure cache dir exists
            Logger.info(f"DadPlayerApp: Art cache directory created: {self.art_cache_dir}")
        else:
            Logger.info(f"DadPlayerApp: Art cache directory found: {self.art_cache_dir}")
        Logger.info("DadPlayerApp: __init__ finished.")


    def build(self):
        Logger.info("DadPlayerApp: Build method started.")
        self.title = f"{APP_NAME} v{APP_VERSION}"

        # self.icons_dir should now be defined from __init__
        if not hasattr(self, 'icons_dir') or not self.icons_dir:
            Logger.error("DadPlayerApp: self.icons_dir is not defined in build method! Check __init__.")
            # Fallback if __init__ somehow failed to set it, though __init__ should run first.
            current_script_path = os.path.dirname(os.path.abspath(__file__))
            self.assets_dir = os.path.join(current_script_path, "..", "assets")
            self.icons_dir = os.path.join(self.assets_dir, "icons")
            Logger.warning(f"DadPlayerApp: Attempted fallback for icons_dir: {self.icons_dir}")


        app_icon_path = get_app_icon_path(self.icons_dir)
        if app_icon_path:
            self.icon = app_icon_path
            Logger.info(f"DadPlayerApp: App icon set to {app_icon_path}")
        else:
            Logger.warning(f"DadPlayerApp: App icon not found in {self.icons_dir}.")


        if not self.player_engine:
             Logger.critical("DadPlayerApp: PlayerEngine is None in build method. Aborting UI build.")
             return Label(text="Critical Error: Player Engine failed to initialize.\nPlease ensure VLC is installed correctly.", halign='center', valign='middle')

        _ = get_placeholder_album_art_path(self.icons_dir)
        Logger.info("DadPlayerApp: Placeholder album art path processed.")

        # --- ENHANCED LOADING FOR common_widgets.kv ---
        common_widgets_kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kv", "common_widgets.kv")
        Logger.info(f"DadPlayerApp: Attempting to load common_widgets.kv from absolute path: {common_widgets_kv_path}")

        if os.path.exists(common_widgets_kv_path):
            Logger.info(f"DadPlayerApp: common_widgets.kv EXISTS at {common_widgets_kv_path}")
            try:
                Builder.load_file(common_widgets_kv_path)
                Logger.info(f"DadPlayerApp: Successfully loaded KV file: {common_widgets_kv_path}")
            except Exception as e_load:
                Logger.error(f"DadPlayerApp: ERROR loading {common_widgets_kv_path}: {e_load}", exc_info=True)
        else:
            Logger.error(f"DadPlayerApp: CRITICAL - common_widgets.kv not found at {common_widgets_kv_path}. Widget styles will be missing.")
        # --- END ENHANCED LOADING ---

        main_app_kv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kv", "main_app.kv")
        Logger.info(f"DadPlayerApp: Attempting to load main_app.kv from: {main_app_kv_path}")
        if os.path.exists(main_app_kv_path):
            try:
                Builder.load_file(main_app_kv_path)
                Logger.info(f"DadPlayerApp: Successfully loaded KV file: {main_app_kv_path}")
            except Exception as e_main_load:
                Logger.error(f"DadPlayerApp: ERROR loading {main_app_kv_path}: {e_main_load}", exc_info=True)
                return Label(text=f"Error loading main_app.kv:\n{e_main_load}") # Critical if main_app.kv fails
        else:
            Logger.error(f"DadPlayerApp: CRITICAL - main_app.kv not found at {main_app_kv_path}. Cannot build UI.")
            return Label(text=f"CRITICAL: main_app.kv not found at\n{main_app_kv_path}")

        self.screen_manager = ScreenManager()
        Logger.info("DadPlayerApp: ScreenManager initialized.")

        try:
            from dad_player.ui.screens.main_screen import MainScreen # Import locally to avoid circular issues if any
            main_screen = MainScreen(
                name='main_screen',
                player_engine=self.player_engine,
                library_manager=self.library_manager,
                settings_manager=self.settings_manager
            )
            self.screen_manager.add_widget(main_screen)
            self.screen_manager.current = 'main_screen'
            Logger.info("DadPlayerApp: MainScreen added to ScreenManager.")
        except Exception as e_ms:
            Logger.error(f"DadPlayerApp: Failed to load MainScreen: {e_ms}", exc_info=True)
            error_label = Label(text=f"Error loading main screen:\n{str(e_ms)[:500]}",
                                halign='center', valign='middle',
                                text_size=(Window.width * 0.8 if Window else 500, None))
            error_screen = Screen(name='error_screen')
            error_screen.add_widget(error_label)
            self.screen_manager.add_widget(error_screen)
            self.screen_manager.current = 'error_screen'
            Logger.critical("DadPlayerApp: Displaying error screen due to MainScreen load failure.")

        Window.bind(on_drop_file=self.handle_dropped_file_app)
        Logger.info("DadPlayerApp: Build method finished successfully.")
        return self.screen_manager

    def handle_dropped_file_app(self, window_instance, file_path_bytes, x, y, *args):
        Logger.info("DadPlayerApp: Entered handle_dropped_file_app")
        try:
            file_path = file_path_bytes.decode('utf-8')
            Logger.info(f"DadPlayerApp: File dropped: {file_path} at ({x}, {y})")

            if not self.player_engine:
                Logger.error("DadPlayerApp: PlayerEngine not available to play dropped file.")
                return

            supported_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
            if file_path.lower().endswith(supported_extensions):
                Logger.info(f"DadPlayerApp: Attempting to load and play dropped file: {file_path}")
                success = self.player_engine.load_media(file_path, play_immediately=True)
                if success:
                    self.switch_to_now_playing_tab()
                else:
                    Logger.error(f"DadPlayerApp: Failed to load dropped file: {file_path} via PlayerEngine.")
            else:
                Logger.warning(f"DadPlayerApp: Dropped file is not a recognized audio type: {file_path}")

        except Exception as e:
            Logger.error(f"DadPlayerApp: Error processing dropped file: {e}", exc_info=True)


    def on_start(self):
        Logger.info(f"{APP_NAME} v{APP_VERSION} started.")
        Clock.schedule_once(self._initial_library_check, 1)

    def _initial_library_check(self, dt=None):
        if self.library_manager and self.settings_manager:
            music_folders = self.settings_manager.get_music_folders()
            try:
                artists = self.library_manager.get_all_artists()
            except AttributeError as e:
                Logger.error(f"DadPlayerApp: LibraryManager missing get_all_artists method: {e}")
                artists = []
            except Exception as e:
                Logger.error(f"DadPlayerApp: Error checking library during initial check: {e}")
                artists = []

            main_screen_instance = self.get_screen_instance('main_screen')
            if not main_screen_instance or isinstance(main_screen_instance, Screen) and main_screen_instance.name == 'error_screen':
                 Logger.warning("DadPlayerApp [_initial_library_check]: MainScreen not available or is error screen. Skipping initial scan prompt update.")
                 return

            if hasattr(main_screen_instance, 'set_initial_scan_prompt'):
                if music_folders and not artists:
                    Logger.info("DadPlayerApp: Music folders are set but library appears empty. Suggesting scan.")
                    main_screen_instance.set_initial_scan_prompt("Library empty. Add folders and scan in Settings.")
                elif not music_folders:
                    Logger.info("DadPlayerApp: No music folders configured.")
                    main_screen_instance.set_initial_scan_prompt("No music folders. Please add folders in Settings.")
            else:
                Logger.warning("DadPlayerApp: MainScreen instance does not have 'set_initial_scan_prompt'.")


    def on_stop(self):
        Logger.info(f"{APP_NAME} stopping...")
        if self.player_engine:
            current_vlc_volume = self.player_engine.get_volume()
            if self.settings_manager:
                self.settings_manager.set_last_volume(float(current_vlc_volume / 100.0))
            self.player_engine.shutdown()
        if self.library_manager and hasattr(self.library_manager, 'stop_scan_music_library'):
            self.library_manager.stop_scan_music_library()
        Logger.info(f"{APP_NAME} stopped.")

    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def open_app_settings(self):
        Logger.info("DadPlayerApp: open_app_settings() called.")
        try:
            from dad_player.ui.popups.settings_popup import PlayerSettingsPopup
            if self.player_engine and self.settings_manager and self.library_manager:
                popup = PlayerSettingsPopup(
                    player_engine=self.player_engine,
                    settings_manager=self.settings_manager,
                    library_manager=self.library_manager,
                    title="Player Settings"
                )
                popup.open()
            else:
                Logger.error("DadPlayerApp: Cannot open settings, core components not ready.")
        except Exception as e:
            Logger.error(f"DadPlayerApp: Error opening settings popup: {e}", exc_info=True)

    def get_screen_instance(self, screen_name):
        if self.screen_manager and self.screen_manager.has_screen(screen_name):
            return self.screen_manager.get_screen(screen_name)
        return None

    def switch_to_now_playing_tab(self):
        main_screen = self.get_screen_instance('main_screen')
        if main_screen and hasattr(main_screen, 'switch_to_tab'):
            Logger.info("DadPlayerApp: Calling switch_to_tab('Now Playing')")
            main_screen.switch_to_tab("Now Playing")
        else:
            Logger.warning("DadPlayerApp: Could not switch to Now Playing tab. MainScreen or method not available.")

    def refresh_library_view_if_current(self):
        main_screen = self.get_screen_instance('main_screen')
        if main_screen and hasattr(main_screen, 'refresh_visible_library_content'):
            main_screen.refresh_visible_library_content()

    def global_scan_progress_update(self, progress_float, message_str, is_done_bool):
        Logger.info(f"AppScanProgress: {message_str} (Done: {is_done_bool}, Progress: {progress_float:.2f})")

        settings_popup_instance = None
        for window_child in Window.children:
            if isinstance(window_child, Popup) and hasattr(window_child, 'title') and window_child.title == "Player Settings":
                from dad_player.ui.popups.settings_popup import PlayerSettingsPopup
                if isinstance(window_child, PlayerSettingsPopup):
                    settings_popup_instance = window_child
                    break

        if settings_popup_instance:
            if hasattr(settings_popup_instance, 'scan_status_text'):
                 settings_popup_instance.scan_status_text = message_str
            if hasattr(settings_popup_instance, '_update_scan_controls_state'):
                settings_popup_instance._update_scan_controls_state()

        if is_done_bool:
            self.refresh_library_view_if_current()

def check_for_null_bytes(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            if b'\x00' in content:
                print(f"ERROR: Null bytes found in {filepath}")
                # You can also try to print the byte offset
                # for i, byte in enumerate(content):
                #     if byte == 0:
                #         print(f"  Null byte at offset: {i}")
                #         break
            else:
                print(f"SUCCESS: No null bytes in {filepath}")
    except Exception as e:
        print(f"Could not read {filepath}: {e}")

# List all your Python files here
python_files = [
    'main_dad_player.py',
    'dad_player/app.py',
    'dad_player/config_manager.py',
    'dad_player/constants.py',
    'dad_player/core/image_utils.py',
    'dad_player/core/library_manager.py',
    'dad_player/core/player_engine.py',
    'dad_player/core/settings_manager.py',
    'dad_player/ui/screens/main_screen.py',
    'dad_player/ui/screens/now_playing_view.py',
    'dad_player/ui/screens/library_view.py',
    'dad_player/ui/screens/playlist_view.py',
    'dad_player/utils.py',
    'test_import.py' # If this is a local test file
]

for py_file in python_files:
    check_for_null_bytes(py_file)

