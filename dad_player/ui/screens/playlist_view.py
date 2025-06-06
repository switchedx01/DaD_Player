# dad_player/ui/screens/playlist_view.py
import os
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ObjectProperty, ListProperty, StringProperty
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.app import App
from kivy.clock import Clock

from dad_player.utils import spx, format_duration
from dad_player.core.image_utils import get_placeholder_album_art_path
from dad_player.constants import ALBUM_ART_LIST_SIZE # For art in list items
from dad_player.ui.widgets.song_list_item import SongListItem


kv_path = os.path.join(os.path.dirname(__file__), "..", "..", "kv", "playlist_view.kv")
if os.path.exists(kv_path):
    Builder.load_file(kv_path)
else:
    Logger.error(f"PlaylistView: KV file not found at {kv_path}")

class PlaylistView(BoxLayout):
    """
    View for displaying and managing the current playback queue (playlist).
    """
    player_engine = ObjectProperty(None)
    library_manager = ObjectProperty(None)

    playlist_data = ListProperty([])
    status_text = StringProperty("Playlist is empty.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._placeholder_art = None
        Clock.schedule_once(self._post_init_setup)

        if self.player_engine:
            self.player_engine.bind(
                on_playlist_changed=self.refresh_playlist_display,
                on_playback_started=self._highlight_current_song_in_playlist, # Highlight new song
                on_playback_stopped=self._unhighlight_all_songs_in_playlist, # Unhighlight if stopped
                on_playback_finished=self._highlight_current_song_in_playlist, # Will be next song or none
                on_shuffle_mode_changed=lambda instance, value: self.refresh_playlist_display() # Re-fetch ordered list
            )

    def _post_init_setup(self, dt=None):
        app = App.get_running_app()
        if app and hasattr(app, 'icons_dir'):
            self._placeholder_art = get_placeholder_album_art_path(app.icons_dir)
        else: # Fallback if app or icons_dir isn't ready
            assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "assets")
            icons_dir = os.path.join(assets_dir, "icons")
            self._placeholder_art = get_placeholder_album_art_path(icons_dir)
        
        self.refresh_playlist_display() # Initial population

    def on_enter(self, *args):
        """Called when this view becomes active (e.g., tab selected)."""
        Logger.info("PlaylistView: Entered.")
        self.refresh_playlist_display()

    def refresh_playlist_display(self, *args):
        Logger.info("PlaylistView: Refreshing playlist display.")
        self.playlist_data = []
        if not self.player_engine or not hasattr(self.player_engine, 'get_current_playlist_details'):
            Logger.warning("PlaylistView: PlayerEngine not available or doesn't support get_current_playlist_details.")
            self.status_text = "Playlist feature not fully available."
            self._update_rv_data()
            return

        current_queue_details = self.player_engine.get_current_playlist_details()

        if not current_queue_details:
            self.status_text = "Playlist is empty."
        else:
            self.status_text = ""
            temp_data = []
            current_playing_filepath = self.player_engine.current_media_path

            for idx, track_info in enumerate(current_queue_details):
                art_path_for_item = self._placeholder_art # Default
                # Future: If library_manager and track_id exist, try to get cached art
                # if self.library_manager and track_info.get('track_id'):
                #     album_id = self.library_manager.get_album_id_for_track(track_info['track_id'])
                #     if album_id:
                #         art_path_for_item = self.library_manager.get_album_art_path(album_id) or self._placeholder_art
                
                item = {
                    'track_id': track_info.get('track_id', idx), # Use index as fallback ID
                    'filepath': track_info['filepath'],
                    'track_number_text': f"{idx + 1}.", # Display 1-based index
                    'song_title_text': track_info.get('title', os.path.basename(track_info['filepath'])),
                    'artist_name_text': track_info.get('artist', "Unknown Artist"),
                    'duration_text': format_duration(track_info.get('duration', 0)),
                    'art_path': art_path_for_item, 
                    'on_press_callback': self.on_playlist_song_selected,
                    # Determine if this item is the one currently playing
                    'is_playing': (current_playing_filepath == track_info['filepath'] and self.player_engine.is_playing())
                }
                temp_data.append(item)
            self.playlist_data = temp_data
        
        self._update_rv_data()
        # self._highlight_current_song_in_playlist() # Highlight after data is set

    def _highlight_current_song_in_playlist(self, *args):
        if not self.player_engine or not self.player_engine.current_media_path:
            self._unhighlight_all_songs_in_playlist()
            return

        current_path = self.player_engine.current_media_path
        needs_refresh = False
        for item_data in self.playlist_data:
            is_now_playing = (item_data['filepath'] == current_path and self.player_engine.is_playing())
            if item_data.get('is_playing') != is_now_playing:
                item_data['is_playing'] = is_now_playing
                needs_refresh = True
        
        if needs_refresh:
            self._update_rv_data()
        
    def _unhighlight_all_songs_in_playlist(self, *args):
        needs_refresh = False
        for item_data in self.playlist_data:
            if item_data.get('is_playing'):
                item_data['is_playing'] = False
                needs_refresh = True
        if needs_refresh:
            self._update_rv_data()

    def _update_rv_data(self):
        playlist_rv = self.ids.get('playlist_rv')
        if playlist_rv:
            playlist_rv.data = self.playlist_data # Assign the new list
            # playlist_rv.refresh_from_data()
        else:
            Logger.warning("PlaylistView: 'playlist_rv' RecycleView not found in ids.")

    def on_playlist_song_selected(self, track_id_or_idx_in_data, song_title):
        """
        Called when a song in the playlist is clicked.
        'track_id_or_idx_in_data' here is the 'track_id' from the item data, which
        we set as the original index in the player_engine's list if no DB ID.
        """
        Logger.info(f"PlaylistView: Song selected - Original Index: {track_id_or_idx_in_data}, Title: {song_title}")
        if self.player_engine and hasattr(self.player_engine, 'play_from_playlist_by_index'):
            # The 'track_id' in playlist_data was set to be the original 0-based index
            # from the player_engine's get_current_playlist_details() list.
            original_playlist_index = track_id_or_idx_in_data 
            
            if self.player_engine.play_from_playlist_by_index(original_playlist_index):
                 app = App.get_running_app()
                 if app and hasattr(app, 'switch_to_now_playing_tab'):
                    app.switch_to_now_playing_tab()
            else:
                Logger.warning(f"PlaylistView: Failed to play song at index {original_playlist_index}")

    def on_clear_playlist_button_press(self):
        Logger.info("PlaylistView: Clear Playlist button pressed.")
        if self.player_engine and hasattr(self.player_engine, 'clear_playlist'):
            self.player_engine.clear_playlist()
            # on_playlist_changed event from player_engine should trigger refresh_playlist_display

    def on_shuffle_playlist_button_press(self):
        Logger.info("PlaylistView: Shuffle Playlist button pressed.")
        if self.player_engine and hasattr(self.player_engine, 'set_shuffle_mode'):
            new_shuffle_state = not self.player_engine.shuffle_mode # Toggle
            self.player_engine.set_shuffle_mode(new_shuffle_state)
            shuffle_button = self.ids.get('shuffle_playlist_button')
            if shuffle_button:
                shuffle_button.icon_color_normal = [0.1, 0.7, 0.9, 1] if new_shuffle_state else [0.9, 0.9, 0.9, 1]


