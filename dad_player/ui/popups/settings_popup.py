# dad_player/ui/popups/settings_popup.py
import os
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.properties import ObjectProperty, BooleanProperty, StringProperty, NumericProperty
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.app import App # For accessing app instance if needed

from dad_player.utils import spx
from dad_player.constants import (
    APP_VERSION, REPEAT_NONE, REPEAT_SONG, REPEAT_PLAYLIST, REPEAT_MODES_TEXT
)
# Import ManageFoldersPopup later to avoid circular dependencies if it also imports this.
# from .manage_folders_popup import ManageFoldersPopup 

# Load KV file for this popup
kv_path = os.path.join(os.path.dirname(__file__), "..", "..", "kv", "settings_popup.kv")
if os.path.exists(kv_path):
    Builder.load_file(kv_path)
else:
    Logger.error(f"PlayerSettingsPopup: KV file not found at {kv_path}")


class PlayerSettingsPopup(Popup):
    player_engine = ObjectProperty(None)
    settings_manager = ObjectProperty(None)
    library_manager = ObjectProperty(None)

    # Properties to bind to UI elements in KV
    autoplay_active = BooleanProperty(False)
    shuffle_active = BooleanProperty(False)
    repeat_mode_text = StringProperty("Repeat: Off")
    current_repeat_mode = NumericProperty(0) # Store the numeric mode

    scan_status_text = StringProperty("")

    def __init__(self, player_engine, settings_manager, library_manager, **kwargs):
        super().__init__(**kwargs)
        self.player_engine = player_engine
        self.settings_manager = settings_manager
        self.library_manager = library_manager

        # Load initial settings values when popup is created
        self.load_settings_values()

        # Bind to library manager's scanning state if possible (requires LibraryManager to be EventDispatcher or have properties)
        if self.library_manager:
            # Assuming LibraryManager might have an 'is_scanning' Kivy property
            # Or we check its state when the popup opens / periodically
            if hasattr(self.library_manager, 'bind'): # Check if it's an EventDispatcher
                 try:
                    self.library_manager.bind(is_scanning=self._update_scan_button_state)
                 except Exception as e:
                    Logger.warning(f"PlayerSettingsPopup: Could not bind to library_manager.is_scanning: {e}")
            self._update_scan_button_state() # Initial check

    def on_open(self):
        """Called when the popup is opened. Refresh settings values."""
        self.load_settings_values()
        self._update_scan_button_state()


    def load_settings_values(self):
        """Loads current settings from managers and updates UI properties."""
        if self.settings_manager:
            self.autoplay_active = self.settings_manager.get_autoplay()
            self.shuffle_active = self.settings_manager.get_shuffle()
            self.current_repeat_mode = self.settings_manager.get_repeat_mode()
            self.repeat_mode_text = REPEAT_MODES_TEXT.get(self.current_repeat_mode, "Repeat: Unknown")
        else:
            Logger.warning("PlayerSettingsPopup: SettingsManager not available.")
        
        self._update_scan_status_text()


    def _update_scan_status_text(self):
        if self.library_manager and self.library_manager.is_scanning:
            # If library_manager has a progress message property, use it
            if hasattr(self.library_manager, 'scan_progress_message') and self.library_manager.scan_progress_message:
                self.scan_status_text = self.library_manager.scan_progress_message
            else:
                self.scan_status_text = "Scan in progress..."
        else:
            self.scan_status_text = "" # Clear if not scanning

    def _update_scan_button_state(self, *args):
        """Updates the scan buttons' disabled state and status text."""
        self._update_scan_status_text() # Update text first
        scan_in_progress = self.library_manager.is_scanning if self.library_manager else False
        
        scan_button = self.ids.get('scan_library_button_settings')
        full_scan_button = self.ids.get('full_scan_library_button_settings')

        if scan_button:
            scan_button.disabled = scan_in_progress
        if full_scan_button:
            full_scan_button.disabled = scan_in_progress


    def on_autoplay_active(self, instance, value):
        if self.settings_manager:
            self.settings_manager.set_autoplay(value)
            Logger.info(f"SettingsPopup: Autoplay set to {value}")
            if self.player_engine and hasattr(self.player_engine, 'set_autoplay_mode'):
                self.player_engine.set_autoplay_mode(value)


    def on_shuffle_active(self, instance, value):
        if self.settings_manager:
            self.settings_manager.set_shuffle(value)
            Logger.info(f"SettingsPopup: Shuffle set to {value}")
            if self.player_engine and hasattr(self.player_engine, 'set_shuffle_mode'):
                self.player_engine.set_shuffle_mode(value) # PlayerEngine will handle playlist reorder


    def cycle_repeat_mode(self):
        if self.settings_manager:
            new_mode = (self.current_repeat_mode + 1) % 3 
            self.settings_manager.set_repeat_mode(new_mode)
            self.current_repeat_mode = new_mode 
            self.repeat_mode_text = REPEAT_MODES_TEXT.get(new_mode, "Repeat: Unknown")
            Logger.info(f"SettingsPopup: Repeat mode set to {new_mode}")
            if self.player_engine and hasattr(self.player_engine, 'set_repeat_mode'):
                self.player_engine.set_repeat_mode(new_mode)


    def open_manage_folders_popup(self):
        Logger.info("SettingsPopup: Opening Manage Folders Popup.")
        from .manage_folders_popup import ManageFoldersPopup # Lazy import
        
        if self.settings_manager and self.library_manager:
            # Pass a callback to ManageFoldersPopup so it can notify SettingsPopup
            # if a rescan is initiated from there, allowing this popup to update its scan status.
            popup = ManageFoldersPopup(
                settings_manager=self.settings_manager,
                library_manager=self.library_manager,
                title="Manage Music Folders"
                # on_scan_triggered_callback=self._update_scan_button_state # Optional: if MFP directly triggers scan
            )
            popup.open()
        else:
            Logger.error("SettingsPopup: Cannot open Manage Folders, core components missing.")

    def start_library_scan(self, full_rescan=False):
        if self.library_manager and not self.library_manager.is_scanning:
            self.scan_status_text = "Scan starting..."
            self._update_scan_button_state() # Disable buttons
            Logger.info(f"SettingsPopup: Starting library scan (Full: {full_rescan}).")
            
            app = App.get_running_app()
            progress_cb = app.global_scan_progress_update if app and hasattr(app, 'global_scan_progress_update') else self._scan_progress_update_ui

            self.library_manager.start_scan_music_library(
                progress_callback=progress_cb, # Use global app callback
                full_rescan=full_rescan
            )
        elif self.library_manager and self.library_manager.is_scanning:
            self.scan_status_text = "Scan already in progress."
            Logger.info("SettingsPopup: Scan attempt while already scanning.")
        else:
            Logger.error("SettingsPopup: LibraryManager not available to start scan.")
            self.scan_status_text = "Error: Library manager unavailable."

    def _scan_progress_update_ui(self, progress_float, message_str, is_done_bool):
        """Callback for library scan progress to update UI within this popup."""
        self.scan_status_text = message_str
        if is_done_bool:
            Logger.info(f"SettingsPopup: Scan finished (notified via local callback). Message: {message_str}")
            self._update_scan_button_state() # Re-enable buttons
            # Refresh library view in the main app
            app = App.get_running_app()
            if app and hasattr(app, 'refresh_library_view_if_current'):
                 app.refresh_library_view_if_current()


    def show_cli_info_popup(self):
        content = BoxLayout(orientation='vertical', padding=spx(10), spacing=spx(10))
        text_content = (
            "To run in Command Line Interface (CLI) mode:\n\n"
            "1. Close this GUI application.\n"
            "2. Open your system's terminal or command prompt.\n"
            "3. Navigate to the DAD Player project directory.\n"
            "   (e.g., `cd path/to/dad_player_project`)\n"
            "4. Run the command: `python main_dad_player.py --cli`"
        )
        info_label = Label(
            text=text_content,
            font_size=spx(13),
            halign='left',
            valign='top'
        )
        info_label.bind(texture_size=info_label.setter('size')) 
        
        close_button = Button(text="Close", size_hint_y=None, height=spx(40))
        
        content.add_widget(info_label)
        content.add_widget(close_button)

        popup = Popup(
            title="CLI Mode Instructions",
            content=content,
            size_hint=(0.8, 0.6)
        )
        close_button.bind(on_release=popup.dismiss)
        popup.open()

