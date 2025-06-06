# dad_player/ui/popups/manage_folders_popup.py
import os
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, ListProperty, StringProperty
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.uix.filechooser import FileChooserListView
from kivy.app import App

from dad_player.utils import spx

kv_path = os.path.join(os.path.dirname(__file__), "..", "..", "kv", "manage_folders_popup.kv")
if os.path.exists(kv_path):
    Builder.load_file(kv_path)
else:
    Logger.error(f"ManageFoldersPopup: KV file not found at {kv_path}")


class FolderChooserPopup(Popup):
    """A popup for choosing a folder."""
    on_folder_selected = ObjectProperty(None)

    def __init__(self, initial_path=None, on_folder_selected=None, **kwargs):
        super().__init__(**kwargs)
        self.on_folder_selected = on_folder_selected
        Logger.info(f"FolderChooserPopup: Initialized with on_folder_selected: {self.on_folder_selected}")

        # self.title = "Select Music Folder"
        # self.size_hint = (0.9, 0.9)
        
        start_path = initial_path or os.path.expanduser("~")
        if not os.path.isdir(start_path): 
            start_path = os.path.abspath(os.sep)

        file_chooser_widget = self.ids.get('folder_chooser_fc')
        if file_chooser_widget:
            file_chooser_widget.path = start_path
        else:
            Logger.error("FolderChooserPopup: FileChooser with id 'folder_chooser_fc' not found in KV.")

    def _on_select_folder(self):
        file_chooser_widget = self.ids.get('folder_chooser_fc')
        if not file_chooser_widget:
            self.dismiss()
            return
        selected_paths = file_chooser_widget.selection
        Logger.info(f"FolderChooserPopup: Selected paths: {selected_paths}")
        if selected_paths and os.path.isdir(selected_paths[0]):
            Logger.info(f"FolderChooserPopup: on_folder_selected value: {self.on_folder_selected}")
            if callable(self.on_folder_selected):
                try:
                    Logger.info("FolderChooserPopup: Calling on_folder_selected callback")
                    self.on_folder_selected(selected_paths[0])
                except Exception as e:
                    Logger.error(f"FolderChooserPopup: Error in on_folder_selected callback: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                Logger.warning("FolderChooserPopup: on_folder_selected callback is not callable")
            self.dismiss()
        else:
            Logger.warning("FolderChooserPopup: No valid folder selected or method not bound correctly.")
            self.dismiss()

class ManageFoldersPopup(Popup):
    settings_manager = ObjectProperty(None)
    library_manager = ObjectProperty(None) 

    music_folders_data = ListProperty([]) 
    status_message = StringProperty("")

    def __init__(self, settings_manager, library_manager, **kwargs):
        super().__init__(**kwargs)
        self.settings_manager = settings_manager
        self.library_manager = library_manager
        self.load_music_folders()

    def load_music_folders(self):
        if self.settings_manager:
            folders = self.settings_manager.get_music_folders()
            self.music_folders_data = [{'path': folder, 'root_popup': self} for folder in folders]
            if not folders:
                self.status_message = "No music folders added yet."
            else:
                self.status_message = ""
            Logger.info(f"ManageFoldersPopup: Loaded music folders: {folders}")
            Logger.error("ManageFoldersPopup: SettingsManager not available.")
            self.status_message = "Error: Settings manager unavailable."

        folders_rv = self.ids.get('folders_rv')
        if folders_rv:
            folders_rv.data = self.music_folders_data
            folders_rv.refresh_from_data()

    def open_folder_chooser(self):
        default_music_path = os.path.join(os.path.expanduser("~"), "Music")
        if not os.path.isdir(default_music_path):
            default_music_path = os.path.expanduser("~")

        chooser_popup = FolderChooserPopup(
            initial_path=default_music_path,
            on_folder_selected=self.add_selected_folder
        )
        Logger.info(f"ManageFoldersPopup: on_folder_selected callback set to: {chooser_popup.on_folder_selected}")
        chooser_popup.open()

    def add_selected_folder(self, folder_path):
        if self.settings_manager:
            Logger.info(f"ManageFoldersPopup: Attempting to add folder: {folder_path}")
            Logger.info(f"ManageFoldersPopup: Settings Manager instance: {self.settings_manager}")
            
            # Log folders BEFORE attempting to add
            current_folders = self.settings_manager.get_music_folders()
            Logger.info(f"ManageFoldersPopup: Current folders before add: {current_folders}")
            
            success = self.settings_manager.add_music_folder(folder_path)
            Logger.info(f"ManageFoldersPopup: add_music_folder returned: {success}")
            
            # Log folders AFTER attempting to add
            updated_folders = self.settings_manager.get_music_folders()
            Logger.info(f"ManageFoldersPopup: Folders after add attempt: {updated_folders}")
            
            if success:
                self.status_message = f"Added: {os.path.basename(folder_path)}"
                self.load_music_folders()
                Logger.info(f"ManageFoldersPopup: music_folders_data after adding: {self.music_folders_data}")
                self._ask_for_rescan("Folder added. Rescan library now?")
            else:
                error_message = getattr(self.settings_manager, 'last_error', "Unknown error")
                self.status_message = f"Could not add: {os.path.basename(folder_path)}. {error_message}"
                Logger.warning(f"ManageFoldersPopup: Failed to add folder. Error: {error_message}")
        else:
            self.status_message = "Error: Settings manager unavailable."

    def remove_folder_from_list_item(self, folder_path_to_remove):
        """Removes a folder, called from FolderListItem's button."""
        if self.settings_manager:
            if self.settings_manager.remove_music_folder(folder_path_to_remove):
                self.status_message = f"Removed: {os.path.basename(folder_path_to_remove)}"
                self.load_music_folders() 
                self._ask_for_rescan("Folder removed. Rescan library now to reflect changes?")
            else:
                self.status_message = f"Folder not found: {os.basename(folder_path_to_remove)}"
        else:
            self.status_message = "Error: Settings manager unavailable."
            
    def _ask_for_rescan(self, message):
        from kivy.uix.button import Button 
        from kivy.uix.label import Label
        
        content = BoxLayout(orientation='vertical', spacing=spx(10), padding=spx(10))
        content.add_widget(Label(text=message, halign='center', font_size=spx(14)))
        
        buttons_layout = BoxLayout(size_hint_y=None, height=spx(40), spacing=spx(10))
        rescan_button = Button(text="Rescan Now (Full)")
        no_button = Button(text="Later")
        
        buttons_layout.add_widget(rescan_button)
        buttons_layout.add_widget(no_button)
        content.add_widget(buttons_layout)
        
        confirm_popup = Popup(title="Rescan Library?", content=content, size_hint=(0.7, 0.3), auto_dismiss=False)
        
        def _do_rescan(instance):
            confirm_popup.dismiss()
            app = App.get_running_app()
            if app and app.library_manager and not app.library_manager.is_scanning:
                try:
                    Logger.info("ManageFoldersPopup: Triggering full rescan via app's LibraryManager.")
                    if hasattr(app.library_manager, 'start_scan_music_library'):
                        app.library_manager.start_scan_music_library(
                            progress_callback=app.scan_progress_update_global,
                            full_rescan=True
                        )
                        self.dismiss()
                    else:
                        Logger.error("ManageFoldersPopup: LibraryManager missing start_scan_music_library method.")
                        self.status_message = "Error: Library scan method not available."
                except Exception as e:
                    Logger.error(f"ManageFoldersPopup: Unexpected error during rescan: {e}")
                    self.status_message = "Error: Could not trigger rescan."
            elif app and app.library_manager and app.library_manager.is_scanning:
                Logger.info("ManageFoldersPopup: Scan already in progress (triggered from rescan prompt).")
                self.status_message = "Scan already in progress."
            else:
                Logger.error("ManageFoldersPopup: Could not trigger rescan - App or LibraryManager unavailable.")
                self.status_message = "Error: Could not trigger rescan."

        rescan_button.bind(on_release=_do_rescan)
        no_button.bind(on_release=confirm_popup.dismiss)
        confirm_popup.open()


    def _simple_scan_status_update(self, progress, message, is_done):
        self.status_message = message
        if is_done:
            Logger.info(f"ManageFoldersPopup: Direct scan (if initiated from here) completed. Message: {message}")
            self.load_music_folders() 
            app = App.get_running_app()
            if app and hasattr(app, 'refresh_library_view_if_current'):
                 app.refresh_library_view_if_current()
