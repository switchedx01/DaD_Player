import os
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label # Added for debug label
from kivy.properties import ObjectProperty, ListProperty, StringProperty, NumericProperty, BooleanProperty
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.app import App
from dad_player.utils import format_duration, dp, sp
from dad_player.core.image_utils import get_placeholder_album_art_path

KV_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "kv", "library_view.kv")
if os.path.exists(KV_FILE):
    Builder.load_file(KV_FILE)
    Logger.info(f"LibraryView: Successfully loaded KV file: {KV_FILE}")
else:
    Logger.error(f"LibraryView: CRITICAL - KV file not found at {KV_FILE}. UI will be broken.")

from dad_player.ui.widgets.artist_list_item import ArtistListItem
from dad_player.ui.widgets.album_grid_item import AlbumGridItem
from dad_player.ui.widgets.song_list_item import SongListItem


class LibraryView(BoxLayout):
    player_engine = ObjectProperty(None)
    library_manager = ObjectProperty(None)
    settings_manager = ObjectProperty(None)

    artists_data = ListProperty([])
    albums_data = ListProperty([])
    songs_data = ListProperty([])

    current_view_mode = StringProperty("all_albums")
    current_artist_id = NumericProperty(None, allownone=True)
    current_artist_name = StringProperty("")
    current_album_id = NumericProperty(None, allownone=True)
    current_album_name = StringProperty("")

    status_text = StringProperty("Loading library...")
    _was_scanning = BooleanProperty(False)
    _display_path_text = StringProperty("All Albums")

    debug_label = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._placeholder_art = None
        Logger.info("LibraryView [INIT]: Initializing LibraryView.")

        Clock.schedule_once(self._post_init_setup, 0.1)
        self.bind(
            current_view_mode=self._trigger_display_path_update,
            current_artist_name=self._trigger_display_path_update,
            current_album_name=self._trigger_display_path_update,
            size=self._update_debug_label_and_graphics,
            pos=self._update_debug_label_and_graphics
        )
        Clock.schedule_once(lambda dt: self._update_display_path_text(), 0.01)
        Clock.schedule_once(lambda dt: self._update_debug_label(), 0.01)


    def _update_debug_label_and_graphics(self, *args):
        self._update_debug_label()


    def _update_debug_graphics(self, *args):
        pass

    def _update_debug_label(self, *args):
        if self.debug_label:
            if not self.debug_label.parent:
                header_bar = self.ids.get('library_header_bar')
                if header_bar and self.debug_label not in header_bar.children:
                    header_bar.add_widget(self.debug_label)
                elif not header_bar and self.ids.get('main_library_layout') and self.debug_label not in self.ids.main_library_layout.children:
                    self.ids.main_library_layout.add_widget(self.debug_label, index=len(self.ids.main_library_layout.children))
                elif self.debug_label not in self.children and not header_bar and not self.ids.get('main_library_layout'):
                    # Absolute fallback: add to LibraryView itself if header_bar is not found
                    self.add_widget(self.debug_label, index=len(self.children))


            self.debug_label.text = (
                f""
                f"Size: [{int(self.width)}, {int(self.height)}] | " # Use int for cleaner display
                f"ArtistID: {self.current_artist_id} | AlbumID: {self.current_album_id}"
            )

    def on_touch_down(self, touch):
        # Logger.critical(f"LibraryView: TOUCH DOWN at {touch.pos} (Size: {self.size}, Pos: {self.pos})")
        # detailed_log = ["LibraryView: TOUCH DOWN DETAILS:"]
        # detailed_log.append(f"  Touch Pos: {touch.pos}, Profile: {touch.profile}")
        # detailed_log.append(f"  Self  Pos: {self.pos}, Size: {self.size}, Disabled: {self.disabled}")

        # if self.ids:
        #     for child_id, child_widget in self.ids.items():
        #         if hasattr(child_widget, 'collide_point') and child_widget.collide_point(*touch.pos):
        #             detailed_log.append(f"  >>> Touch OVERLAPS child ID: '{child_id}' (Widget: {child_widget}, Disabled: {child_widget.disabled if hasattr(child_widget, 'disabled') else 'N/A'})")
        # else:
        #     detailed_log.append("  Self.ids is empty.")
        # Logger.critical("\n".join(detailed_log))
        '''

        The previous line was used in terminal logging for debug, can be added later to ensure things are operating correctly

        '''
        return super().on_touch_down(touch)

    def _trigger_display_path_update(self, *args):
        self._update_display_path_text()

    def _update_display_path_text(self, *args):
        if self.current_view_mode == 'albums_for_artist':
            self._display_path_text = self.current_artist_name if self.current_artist_name else "Artist Albums"
        elif self.current_view_mode == 'songs_for_album':
            self._display_path_text = self.current_album_name if self.current_album_name else "Album Songs"
        elif self.current_view_mode == 'artists':
            self._display_path_text = "All Artists"
        elif self.current_view_mode == 'all_albums': # Default view
            self._display_path_text = "All Albums"
        else:
            self._display_path_text = "Library" # Fallback
        Logger.debug(f"LibraryView [_update_display_path_text]: Display path set to: '{self._display_path_text}' (Mode: {self.current_view_mode})")
        self._update_debug_label()


    def _post_init_setup(self, dt=None):
        Logger.info("LibraryView [_post_init_setup]: Post-init setup starting.")
        self._update_debug_label_and_graphics() # Call this early

        if self.debug_label and not self.debug_label.parent:
            header_bar = self.ids.get('library_header_bar')
            if header_bar and self.debug_label not in header_bar.children:
                header_bar.add_widget(self.debug_label, index=len(header_bar.children))
            elif self.ids.get('main_library_layout') and self.debug_label not in self.ids.main_library_layout.children: # Fallback
                self.ids.main_library_layout.add_widget(self.debug_label, index=len(self.ids.main_library_layout.children))
            elif self.debug_label not in self.children: # Absolute fallback
                 self.add_widget(self.debug_label, index=len(self.children))


        app = App.get_running_app()
        if app and hasattr(app, 'icons_dir') and app.icons_dir:
            self._placeholder_art = get_placeholder_album_art_path(app.icons_dir)
        else:
            assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "assets")
            icons_dir = os.path.join(assets_dir, "icons")
            self._placeholder_art = get_placeholder_album_art_path(icons_dir)
            Logger.warning(f"LibraryView [_post_init_setup]: Using fallback placeholder art path logic for icons_dir. Path: {self._placeholder_art}")

        if self.library_manager:
            self._was_scanning = self.library_manager.is_scanning # Store initial state
            self.library_manager.bind(is_scanning=self.on_library_manager_scanning_change)
            # Logger.info("LibraryView [_post_init_setup]: Bound to LibraryManager.is_scanning.")
        else:
            Logger.error("LibraryView [_post_init_setup]: LibraryManager NOT AVAILABLE for binding.")

        self.current_view_mode = "all_albums" # Default view
        self.load_all_albums() # Load initial data
        self._update_display_path_text() # Update breadcrumb
        self._update_debug_label() # Update debug label

        # Initial status message based on library content
        if self.library_manager and self.settings_manager:
            albums_exist = self.library_manager.get_albums_by_artist(artist_id=None) # Check if any albums exist at all
            folders_set = self.settings_manager.get_music_folders()
            if not albums_exist and folders_set:
                self.status_text = "Library is empty. Consider scanning in Settings."
            elif not folders_set:
                self.status_text = "No music folders configured. Please add folders in Settings."
        elif not self.library_manager:
            self.status_text = "Library manager unavailable."
        Logger.info("LibraryView [_post_init_setup]: Post-init setup finished.")


    def on_library_manager_scanning_change(self, instance, current_is_scanning_value):
        Logger.info(f"LibraryView [on_library_manager_scanning_change]: Scanning state changed from {self._was_scanning} to {current_is_scanning_value}")
        if self._was_scanning and not current_is_scanning_value: # Scan just finished
            Logger.info("LibraryView [on_library_manager_scanning_change]: Scan finished. Scheduling view refresh.")
            Clock.schedule_once(lambda dt: self.refresh_library_view(), 0.2)
        self._was_scanning = current_is_scanning_value # Update the tracking state

    def refresh_library_view(self):
        """Refreshes the content of the currently active library view."""
        Logger.info(f"LibraryView [refresh_library_view]: Refreshing view. Mode: {self.current_view_mode}, ArtistID: {self.current_artist_id}, AlbumID: {self.current_album_id}")

        current_mode_before_refresh = self.current_view_mode

        if current_mode_before_refresh == "all_albums":
            self.load_all_albums()
        elif current_mode_before_refresh == "artists":
            self.load_artists()
        elif current_mode_before_refresh == "albums_for_artist":
            if self.current_artist_id is not None: # Ensure context is valid
                self.load_albums_for_artist(self.current_artist_id, self.current_artist_name)
            else: # Fallback if context was lost
                Logger.warning("LibraryView [refresh_library_view]: 'albums_for_artist' mode but current_artist_id is None. Defaulting to all_albums.")
                self.load_all_albums()
        elif current_mode_before_refresh == "songs_for_album":
            if self.current_album_id is not None:
                self.load_songs_for_album(self.current_album_id, self.current_album_name)
            else: # Fallback if context was lost
                Logger.warning("LibraryView [refresh_library_view]: 'songs_for_album' mode but current_album_id is None. Defaulting to all_albums.")
                self.load_all_albums()
        else: # Default or unknown mode
            Logger.warning(f"LibraryView [refresh_library_view]: Unknown mode '{current_mode_before_refresh}'. Defaulting to all_albums.")
            self.load_all_albums()
        self._update_display_path_text() # Ensure breadcrumb is also up-to-date


    def _create_press_action(self, item_type, item_id, item_name_or_title):
        """Helper to create lambda functions for RV item presses."""
        if item_type == "artist":
            return lambda *args: self.on_artist_selected(item_id, item_name_or_title)
        elif item_type == "album":
            return lambda *args: self.on_album_selected(item_id, item_name_or_title)
        elif item_type == "song":
            return lambda *args: self.on_song_selected(item_id, item_name_or_title)
        return None # Should not happen if item_type is always valid

    def load_all_albums(self):
        Logger.info("LibraryView [load_all_albums]: Loading all albums...")
        self.current_view_mode = "all_albums"
        self.current_artist_id = None
        self.current_artist_name = ""
        self.current_album_id = None
        self.current_album_name = ""
        self.albums_data = [] # Clear previous data

        if not self.library_manager:
            Logger.error("LibraryView [load_all_albums]: LibraryManager is None.")
            self.status_text = "Error: Library manager not available."
            self.update_status_and_recycleview_refresh('albums_rv') # Ensure status is updated
            self._update_display_path_text() # Update breadcrumb
            return

        all_albums_from_db = self.library_manager.get_albums_by_artist(artist_id=None)
        if all_albums_from_db:
            temp_albums_data = [
                {
                    'album_id': album['id'],
                    'album_name': album['name'], # Should always exist
                    'artist_name': album.get('artist_name', 'Unknown Artist'), # Handle if artist_name is missing
                    'art_path': album.get('art_path') or self._placeholder_art, # Use placeholder if art_path missing/None
                    'on_press_callback': self._create_press_action("album", album['id'], album['name'])
                } for album in all_albums_from_db
            ]
            self.albums_data = temp_albums_data
            # Logger.debug(f"LibraryView [load_all_albums]: Loaded {len(self.albums_data)} albums.")
        # else:
            # Logger.info("LibraryView [load_all_albums]: No albums found in the database.")
        self.update_status_and_recycleview_refresh('albums_rv')
        self._update_display_path_text() # Update breadcrumb


    def load_artists(self):
        Logger.info("LibraryView [load_artists]: Loading artists...")
        self.current_view_mode = "artists"
        self.current_artist_id = None # Reset context
        self.current_artist_name = ""
        self.current_album_id = None
        self.current_album_name = ""
        self.artists_data = [] # Clear previous

        if not self.library_manager:
            Logger.error("LibraryView [load_artists]: LibraryManager is None.")
            self.status_text = "Error: Library manager not available."
            self.update_status_and_recycleview_refresh('artists_rv')
            self._update_display_path_text()
            return

        artists_from_db = self.library_manager.get_all_artists()
        if artists_from_db:
            temp_artists_data = [
                {
                    'artist_id': artist['id'],
                    'artist_name': artist['name'], # Should always exist
                    'on_press_callback': self._create_press_action("artist", artist['id'], artist['name'])
                } for artist in artists_from_db
            ]
            self.artists_data = temp_artists_data
            # Logger.debug(f"LibraryView [load_artists]: Loaded {len(self.artists_data)} artists.")
        # else:
            # Logger.info("LibraryView [load_artists]: No artists found in the database.")
        self.update_status_and_recycleview_refresh('artists_rv')
        self._update_display_path_text()

    def load_albums_for_artist(self, artist_id, artist_name):
        Logger.info(f"LibraryView [load_albums_for_artist]: Artist ID {artist_id} ('{artist_name}').")
        self.current_view_mode = "albums_for_artist"
        self.current_artist_id = artist_id # Set context
        self.current_artist_name = artist_name
        self.current_album_id = None # Reset deeper context
        self.current_album_name = ""
        self.albums_data = [] # Clear previous

        if not self.library_manager:
            Logger.error(f"LibraryView [load_albums_for_artist]: LibraryManager is None.")
            self.status_text = "Error: Library manager not available."
            self.update_status_and_recycleview_refresh('albums_rv')
            self._update_display_path_text()
            return

        albums_from_db = self.library_manager.get_albums_by_artist(artist_id)
        if albums_from_db:
            temp_albums_data = [
                {
                    'album_id': album['id'],
                    'album_name': album['name'],
                    'artist_name': album.get('artist_name', artist_name), # Fallback to passed artist_name if DB is missing it
                    'art_path': album.get('art_path') or self._placeholder_art,
                    'on_press_callback': self._create_press_action("album", album['id'], album['name'])
                } for album in albums_from_db
            ]
            self.albums_data = temp_albums_data
        self.update_status_and_recycleview_refresh('albums_rv')
        self._update_display_path_text()

    def load_songs_for_album(self, album_id, album_name):
        Logger.info(f"LibraryView [load_songs_for_album]: Preparing songs for Album ID {album_id} ('{album_name}').")
        Logger.info(f"LibraryView: Initial context: self.current_artist_name='{self.current_artist_name}', self.current_artist_id='{self.current_artist_id}'")

        self.current_view_mode = "songs_for_album"
        self.current_album_id = album_id # Set context
        self.current_album_name = album_name
        self.songs_data = [] # Clear previous

        album_art_for_list = self._placeholder_art # Default
        target_album_info = None # To store details of the current album

        if not self.library_manager:
            Logger.error(f"LibraryView [load_songs_for_album]: LibraryManager is None. Cannot load songs.")
            self.status_text = "Error: Library manager not available."
            self.update_status_and_recycleview_refresh('songs_rv') # Refresh RV even on error to clear it / show status
            self._update_display_path_text()
            return

        if self.library_manager:
            all_albums_from_db = self.library_manager.get_albums_by_artist(artist_id=None) # Get all albums to find the current one
            if all_albums_from_db: # Check if the list is not empty
                target_album_info = next((album_dict for album_dict in all_albums_from_db if album_dict['id'] == album_id), None)
                if target_album_info: # Found the album
                    Logger.info(f"LibraryView: Found target_album_info for Album ID {album_id}: {target_album_info}")
                    if target_album_info.get('art_path'):
                        album_art_for_list = target_album_info['art_path']
                        Logger.info(f"LibraryView: Using specific art_path '{album_art_for_list}' for Album ID {album_id}.")
                    else:
                        Logger.warning(f"LibraryView: No 'art_path' in target_album_info for Album ID {album_id}. Using placeholder: {self._placeholder_art}")
                else:
                    Logger.warning(f"LibraryView: Could not find target_album_info for Album ID {album_id} in all_albums_from_db. Using placeholder art and hoping for the best for artist name.")
            else: # No albums returned at all
                Logger.warning(f"LibraryView: Could not fetch any albums from DB to find details for Album ID {album_id}. Using placeholder art.")
        
        # Determine the primary artist for this album
        album_primary_artist_name = "Unknown Artist" # Default
        if target_album_info and target_album_info.get('artist_name') and target_album_info.get('artist_name').lower() != "various artists": # Prioritize specific album artist if not "Various Artists"
            album_primary_artist_name = target_album_info.get('artist_name')
            Logger.info(f"LibraryView: Set album_primary_artist_name='{album_primary_artist_name}' (from target_album_info).")
        elif target_album_info and target_album_info.get('artist_name') and target_album_info.get('artist_name').lower() == "various artists":
            album_primary_artist_name = "Various Artists" # Explicitly set for "Various Artists" albums
            Logger.info(f"LibraryView: Set album_primary_artist_name='Various Artists' (from target_album_info).")
        elif self.current_artist_name and self.current_artist_id is not None: # Fallback to navigation context if relevant
            # This case is useful if target_album_info was missing or had no artist,
            # AND we navigated from a specific artist's page.
            album_primary_artist_name = self.current_artist_name
            Logger.info(f"LibraryView: Set album_primary_artist_name='{album_primary_artist_name}' (from self.current_artist_name as fallback).")
        else:
            Logger.info(f"LibraryView: album_primary_artist_name defaulted/remained 'Unknown Artist'. target_album_info_artist: {target_album_info.get('artist_name') if target_album_info else 'N/A'}, self.current_artist_name: {self.current_artist_name}")


        tracks = self.library_manager.get_tracks_by_album(album_id)
        if tracks:
            temp_songs_data = []
            for i, track in enumerate(tracks):
                track_title = track.get('title', f"Unknown Title {i+1}")
                # Get the artist SPECIFIC to this track from the database query result
                track_specific_artist = track.get('artist_name') # This comes from `ar.name as artist_name` in get_tracks_by_album
                
                artist_name_for_display = album_primary_artist_name # Default to album's primary artist

                # If the track has its own artist listed, and it's not generic, prefer that.
                if track_specific_artist and track_specific_artist.strip() and track_specific_artist.lower() != "unknown artist":
                    artist_name_for_display = track_specific_artist
                
                # --- ENHANCED LOGGING ---
                Logger.info(f"LibraryView: ---- Track {i+1} ('{track_title}') ----")
                Logger.info(f"LibraryView: Raw DB data for track: {track}")
                Logger.info(f"LibraryView: TrackSpecificArtist (from track.get('artist_name')): '{track_specific_artist}'")
                Logger.info(f"LibraryView: AlbumPrimaryArtist (determined before loop): '{album_primary_artist_name}'")
                Logger.info(f"LibraryView: ArtistNameForDisplay (after logic): '{artist_name_for_display}'")
                # --- END ENHANCED LOGGING ---

                track_num = track.get('track_number')
                duration_sec = track.get('duration', 0)

                song_item_data = {
                    'track_id': track['id'], # Should exist
                    'song_title_text': track_title,
                    'track_number_text': f"{track_num:02d}." if isinstance(track_num, int) and track_num > 0 else "",
                    'artist_name_text': artist_name_for_display, # Use the determined artist name
                    'duration_text': format_duration(duration_sec),
                    'art_path': album_art_for_list, # Use consistent art for all songs in this album view
                    'on_press_callback': self._create_press_action("song", track['id'], track_title),
                    'filepath': track.get('filepath') # Make sure filepath is included for player_engine
                }
                temp_songs_data.append(song_item_data)

            self.songs_data = temp_songs_data
            Logger.info(f"LibraryView [load_songs_for_album]: Prepared {len(self.songs_data)} items for songs_rv.")
        else:
            Logger.info(f"LibraryView [load_songs_for_album]: No tracks found for Album ID {album_id}.")


        self.update_status_and_recycleview_refresh('songs_rv') # Refresh RV with new song data
        self._update_display_path_text()


    def update_status_text(self):
        """Updates the status_text based on current view and data."""
        # Check if data lists are empty for the current view mode
        if self.current_view_mode == "all_albums" and not self.albums_data:
            self.status_text = "No albums found. Scan your library in Settings."
        elif self.current_view_mode == "artists" and not self.artists_data:
            self.status_text = "No artists found. Scan your library in Settings."
        elif self.current_view_mode == "albums_for_artist" and not self.albums_data:
            # Only show "No albums for artist" if an artist is actually selected
            self.status_text = f"No albums found for {self.current_artist_name}." if self.current_artist_name else "No albums found."
        elif self.current_view_mode == "songs_for_album" and not self.songs_data:
            # Only show "No songs for album" if an album is actually selected
            self.status_text = f"No songs found in {self.current_album_name}." if self.current_album_name else "No songs found."
        elif (self.albums_data and self.current_view_mode in ["all_albums", "albums_for_artist"]) or \
             (self.artists_data and self.current_view_mode == "artists") or \
             (self.songs_data and self.current_view_mode == "songs_for_album"):
             self.status_text = "" # Clear status if data is present for the current view
        # else: # If none of the above, could be an initial state or undefined view mode
            # self.status_text = "Loading..." # Or some other generic message
        self._update_debug_label() # Keep debug label updated


    def update_status_and_recycleview_refresh(self, intended_rv_id_from_caller=None):
        """
        Updates the status text and refreshes the appropriate RecycleView based on the current_view_mode.
        The intended_rv_id_from_caller is mostly for logging/debugging to see what the caller thought it was updating.
        The actual RV updated is determined by self.current_view_mode.
        """
        self.update_status_text() # Set the status_text first
        self._update_debug_label() # Update debug label

        rv_widget_to_update = None
        data_to_assign = []
        actual_rv_id_to_use = "" # The RV ID that will actually be used based on current_view_mode

        # Determine which RV and data to use based on the current view mode
        if self.current_view_mode == 'artists':
            actual_rv_id_to_use = 'artists_rv'
            data_to_assign = self.artists_data
        elif self.current_view_mode == 'all_albums' or self.current_view_mode == 'albums_for_artist':
            actual_rv_id_to_use = 'albums_rv'
            data_to_assign = self.albums_data
        elif self.current_view_mode == 'songs_for_album':
            actual_rv_id_to_use = 'songs_rv' # Corrected from songs_rv_data
            data_to_assign = self.songs_data
        # else: No RV to update for other modes or if mode is not set

        if actual_rv_id_to_use: # If a valid RV ID was determined
            rv_widget_to_update = self.ids.get(actual_rv_id_to_use)
            if rv_widget_to_update:
                Logger.info(f"LibraryView [update_SRR]: Updating RV '{actual_rv_id_to_use}' with {len(data_to_assign)} items. (Caller intended: {intended_rv_id_from_caller or 'N/A'})")
                rv_widget_to_update.data = data_to_assign
                rv_widget_to_update.refresh_from_data() # Essential after changing data
            else:
                Logger.error(f"LibraryView [update_SRR]: RV widget ID '{actual_rv_id_to_use}' NOT FOUND for mode '{self.current_view_mode}'. Check library_view.kv.")
        # else:
            # Logger.debug(f"LibraryView [update_SRR]: No specific RV to update for mode '{self.current_view_mode}'.")


    def on_artist_selected(self, artist_id, artist_name, *args):
        Logger.info(f"LibraryView [on_artist_selected]: ID: {artist_id}, Name: {artist_name}")
        if artist_id is None or not artist_name: return # Basic validation
        # When an artist is selected, their ID and name become the current context.
        self.current_artist_id = artist_id
        self.current_artist_name = artist_name
        self.current_view_mode = "albums_for_artist" # Change mode before loading
        self.load_albums_for_artist(artist_id, artist_name)

    def on_album_selected(self, album_id, album_name, *args):
        Logger.info(f"LibraryView [on_album_selected]: ID: {album_id}, Name: {album_name}")
        if album_id is None or not album_name: return # Basic validation
    
        self.current_album_id = album_id
        self.current_album_name = album_name
        self.current_view_mode = "songs_for_album" # Change mode before loading
        self.load_songs_for_album(album_id, album_name)


    def on_song_selected(self, track_id, song_title, *args):
        Logger.info(f"LibraryView [on_song_selected]: Track ID: {track_id}, Title: {song_title}")
        if not self.player_engine or not self.library_manager:
            Logger.error("LibraryView [on_song_selected]: PlayerEngine or LibraryManager not available.")
            return

        filepath = self.library_manager.get_track_filepath(track_id)
        if not filepath:
            Logger.error(f"LibraryView [on_song_selected]: Filepath not found for track ID {track_id}")
            return

        if self.current_view_mode == "songs_for_album" and self.songs_data:
            all_filepaths_in_album = [s['filepath'] for s in self.songs_data if 'filepath' in s and s.get('filepath')]
            if not all_filepaths_in_album:
                Logger.warning("LibraryView [on_song_selected]: songs_data present, but no filepaths found. Playing selected song only.")
                self.player_engine.load_media(filepath, play_immediately=True)
            else:
                try:
                    start_index = all_filepaths_in_album.index(filepath)
                    self.player_engine.load_playlist(all_filepaths_in_album, play_index=start_index, clear_current=True)
                except ValueError:
                    Logger.error(f"LibraryView [on_song_selected]: Filepath '{filepath}' not found in album's filepaths. Playing selected song only.")
                    self.player_engine.load_media(filepath, play_immediately=True)
        else:
            self.player_engine.load_media(filepath, play_immediately=True)

        # Switch to Now Playing tab
        app = App.get_running_app()
        if app and hasattr(app, 'switch_to_now_playing_tab'):
            app.switch_to_now_playing_tab()


    def on_play_album_button_press(self):
        if self.current_view_mode == "songs_for_album" and self.current_album_id is not None and self.songs_data:
            Logger.info(f"LibraryView [on_play_album_button_press]: Play Album: {self.current_album_name} (ID: {self.current_album_id})")
            if self.player_engine:
                filepaths = [song['filepath'] for song in self.songs_data if 'filepath' in song and song.get('filepath')] # Ensure filepath exists
                if filepaths:
                    self.player_engine.load_playlist(filepaths, play_index=0, clear_current=True)
                    app = App.get_running_app()
                    if app and hasattr(app, 'switch_to_now_playing_tab'):
                        app.switch_to_now_playing_tab()
                else:
                    Logger.warning("LibraryView [on_play_album_button_press]: No valid filepaths found in current album's songs_data.")
        else:
            Logger.warning(f"LibraryView [on_play_album_button_press]: Button pressed in invalid state. Mode: {self.current_view_mode}, AlbumID: {self.current_album_id}, SongsData: {bool(self.songs_data)}")
        

    def go_back_library_navigation(self):
        Logger.info(f"LibraryView [go_back_library_navigation]: Back. Current mode: {self.current_view_mode}, Artist ID: {self.current_artist_id}, Album ID: {self.current_album_id}")
        if self.current_view_mode == "songs_for_album":
            if self.current_artist_id is not None and self.current_artist_name:
                self.current_view_mode = "albums_for_artist"
                self.load_albums_for_artist(self.current_artist_id, self.current_artist_name)
            else:
                self.current_view_mode = "all_albums"
                self.load_all_albums()
        elif self.current_view_mode == "albums_for_artist":
            # From an artist's album list, back goes to the list of all artists.
            self.current_view_mode = "artists"
            self.load_artists()
        elif self.current_view_mode == "artists":
            # From all artists, back goes to all albums.
            self.current_view_mode = "all_albums"
            self.load_all_albums()
        else: # Default or unknown previous state, go to all_albums
            self.current_view_mode = "all_albums"
            self.load_all_albums()
        self._update_display_path_text() # Update breadcrumb after navigation


    def on_scan_library_button_press(self):
        app = App.get_running_app()
        if app and hasattr(app, 'open_app_settings'):
            app.open_app_settings()
            # The actual scan initiation will be handled within the settings popup.
        else:
            Logger.error("LibraryView [on_scan_library_button_press]: Could not open app settings (app instance or method missing).")
        

    def show_all_artists(self):
        Logger.info("LibraryView [show_all_artists]: Navigating to show all artists.")
        self.current_artist_id = None # Clear specific artist context
        self.current_artist_name = ""
        self.current_view_mode = "artists" # Change mode before loading
        self.load_artists()
        self._update_display_path_text() # Update breadcrumb

    def show_all_albums_view(self): # New method to explicitly switch to all_albums view
        Logger.info("LibraryView [show_all_albums_view]: Navigating to show all albums.")
        self.current_artist_id = None # Clear specific artist context
        self.current_artist_name = ""
        self.current_view_mode = "all_albums" # Change mode before loading
        self.load_all_albums()
        self._update_display_path_text()

