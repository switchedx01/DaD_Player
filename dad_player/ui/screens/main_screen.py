# dad_player/ui/screens/main_screen.py
import os
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem, TabbedPanelHeader
from kivy.uix.label import Label
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import ObjectProperty
from kivy.app import App

from dad_player.utils import spx
from dad_player.constants import ALBUM_ART_NOW_PLAYING_SIZE

now_playing_kv_path = os.path.join(os.path.dirname(__file__), "..", "..", "kv", "now_playing_view.kv")
if os.path.exists(now_playing_kv_path):
    Builder.load_file(now_playing_kv_path)
    Logger.info(f"MainScreen: Successfully loaded EXPLICIT KV file for NowPlayingView: {now_playing_kv_path}")
else:
    Logger.error(f"MainScreen: CRITICAL - KV file for NowPlayingView not found at {now_playing_kv_path}. IDs for NowPlayingView will be missing.")

kv_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "kv", "main_screen.kv")
if os.path.exists(kv_file_path):
    Builder.load_file(kv_file_path)
    Logger.info(f"MainScreen: Successfully loaded KV file for MainScreen: {kv_file_path}")
else:
    Logger.error(f"MainScreen: CRITICAL - KV file for MainScreen not found at {kv_file_path}")


class MainScreen(Screen):
    player_engine = ObjectProperty(None)
    library_manager = ObjectProperty(None)
    settings_manager = ObjectProperty(None)

    def __init__(self, player_engine, library_manager, settings_manager, **kwargs):
        super().__init__(**kwargs)
        self.player_engine = player_engine
        self.library_manager = library_manager
        self.settings_manager = settings_manager
        Logger.info(f"MainScreen [INIT]: PlayerEngine instance: {self.player_engine}")
        self._tabs_populated = False # Initialize flag

    def on_enter(self, *args):
        Logger.info("MainScreen [on_enter]: Entered.")
        
        tab_panel = self.ids.get('main_tab_panel')
        if not tab_panel:
            Logger.error("MainScreen [on_enter]: 'main_tab_panel' not found in ids. KV file might not be loaded correctly or id is missing.")
            self.clear_widgets()
            self.add_widget(Label(text="Error: MainScreen UI failed to load.\nCheck KV file for 'main_tab_panel' ID.",
                                  halign='center', valign='middle', font_size=spx(16)))
            return

        if not self._tabs_populated:
            Logger.info("MainScreen [on_enter]: Tabs not yet populated. Scheduling _populate_tabs.")
            # Schedule _populate_tabs to allow Kivy's main loop to process KV loading fully.
            Clock.schedule_once(self._populate_tabs, 0.1)
        else:
            Logger.info("MainScreen [on_enter]: Tabs already populated.")


    def _populate_tabs(self, dt=None): # Add dt argument for Clock.schedule_once
        Logger.info("MainScreen [_populate_tabs]: Attempting to populate tabs.")
        tab_panel = self.ids.get('main_tab_panel')
        if not tab_panel:
            Logger.error("MainScreen [_populate_tabs]: 'main_tab_panel' still not found. Cannot populate tabs.")
            return

        try:
            from dad_player.ui.screens.now_playing_view import NowPlayingView
            from dad_player.ui.screens.library_view import LibraryView
            from dad_player.ui.screens.playlist_view import PlaylistView

            tab_font_size = spx(13)
            tab_panel.clear_tabs()
            Logger.info("MainScreen [_populate_tabs]: Cleared existing tabs (if any).")

            # Now Playing Tab
            Logger.info("MainScreen [_populate_tabs]: Creating NowPlayingView...")
            np_view = NowPlayingView( # NowPlayingView KV rules should be known by Builder now
                player_engine=self.player_engine,
                library_manager=self.library_manager
            )
            Logger.info(f"MainScreen [_populate_tabs]: Created NowPlayingView instance: {np_view}. Its IDs: {np_view.ids if hasattr(np_view, 'ids') else 'N/A (before add_widget)'}")
            
            np_header = TabbedPanelHeader(text="Now Playing", font_size=tab_font_size)
            np_header.content = np_view # This adds np_view to the widget tree
            tab_panel.add_widget(np_header)
            Logger.info(f"MainScreen [_populate_tabs]: Added Now Playing tab. NowPlayingView parent: {np_view.parent}, IDs after add: {np_view.ids}")


            # Library Tab
            Logger.info("MainScreen [_populate_tabs]: Creating LibraryView...")
            lib_view = LibraryView(
                player_engine=self.player_engine,
                library_manager=self.library_manager,
                settings_manager=self.settings_manager
            )
            lib_header = TabbedPanelHeader(text="Library", font_size=tab_font_size)
            lib_header.content = lib_view
            tab_panel.add_widget(lib_header)
            Logger.info("MainScreen [_populate_tabs]: Added Library tab.")
            
            # Playlist Tab
            Logger.info("MainScreen [_populate_tabs]: Creating PlaylistView...")
            pl_view = PlaylistView(
                player_engine=self.player_engine,
                library_manager=self.library_manager
            )
            pl_header = TabbedPanelHeader(text="Playlist", font_size=tab_font_size)
            pl_header.content = pl_view
            tab_panel.add_widget(pl_header)
            Logger.info("MainScreen [_populate_tabs]: Added Playlist tab.")

            # Set default tab
            if tab_panel.tab_list:
                library_tab_header = next((tab for tab in tab_panel.tab_list if tab.text == "Library"), None)
                if library_tab_header:
                    tab_panel.switch_to(library_tab_header)
                    Logger.info("MainScreen [_populate_tabs]: Switched to Library tab as default.")
                else: # Fallback to first tab if "Library" isn't found (e.g. name typo)
                    tab_panel.switch_to(tab_panel.tab_list[0])
                    Logger.warning("MainScreen [_populate_tabs]: 'Library' tab not found, switched to first tab as default.")
            
            self._tabs_populated = True # Set flag after successful population
            Logger.info("MainScreen [_populate_tabs]: Tabs populated successfully.")

        except ImportError as ie:
            Logger.error(f"MainScreen [_populate_tabs]: ImportError: {ie}. Check circular dependencies or file paths.", exc_info=True)
            tab_panel.clear_tabs()
            tab_panel.add_widget(TabbedPanelHeader(text="Import Error", content=Label(text=f"ImportError: {ie}")))
        except Exception as e:
            Logger.error(f"MainScreen [_populate_tabs]: Unexpected error: {e}", exc_info=True)
            tab_panel.clear_tabs() # Clear partially populated tabs on error
            tab_panel.add_widget(TabbedPanelHeader(text="Error", content=Label(text=f"Error populating tabs: {e}")))


    def open_app_settings(self):
        app = App.get_running_app()
        if app and hasattr(app, 'open_app_settings'):
            app.open_app_settings()
        else:
            Logger.warning("MainScreen: Could not get running app instance or 'open_app_settings' method to open settings.")

    def switch_to_tab(self, tab_text):
        tab_panel = self.ids.get('main_tab_panel')
        if tab_panel:
            target_tab_header = next((tab for tab in tab_panel.tab_list if tab.text == tab_text), None)
            if target_tab_header:
                tab_panel.switch_to(target_tab_header)
                Logger.info(f"MainScreen: Switched to tab: {tab_text}")
                if tab_text == "Now Playing" and hasattr(target_tab_header.content, 'update_ui_from_player_state'):
                    Logger.info("MainScreen: Forcing NowPlayingView UI update on tab switch.")
                    target_tab_header.content.update_ui_from_player_state()
            else:
                Logger.warning(f"MainScreen: Tab '{tab_text}' not found.")
        else:
            Logger.error("MainScreen: 'main_tab_panel' not found in ids when trying to switch tab.")
            
    def refresh_visible_library_content(self):
        tab_panel = self.ids.get('main_tab_panel')
        if tab_panel and tab_panel.current_tab and tab_panel.current_tab.text == "Library":
            library_view_widget = tab_panel.current_tab.content
            if library_view_widget and hasattr(library_view_widget, 'refresh_library_view'):
                Logger.info("MainScreen: Refreshing visible library content.")
                library_view_widget.refresh_library_view()

    def set_initial_scan_prompt(self, message):
        def update_library_status(dt):
            tab_panel = self.ids.get('main_tab_panel')
            if tab_panel:
                library_tab_header = next((tab for tab in tab_panel.tab_list if tab.text == "Library"), None)
                if library_tab_header and library_tab_header.content:
                    library_view_widget = library_tab_header.content
                    if hasattr(library_view_widget, 'status_text'):
                        library_view_widget.status_text = message
                        Logger.info(f"MainScreen: Set initial library prompt: {message}")
        # Schedule this with a slight delay to ensure tabs and their content might be populated
        Clock.schedule_once(update_library_status, 0.5)

