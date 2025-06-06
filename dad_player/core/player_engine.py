import mutagen
import vlc
import time
import threading
import os
import random
from kivy.logger import Logger
from kivy.clock import Clock
from kivy.event import EventDispatcher
from kivy.app import App
from kivy.properties import ObjectProperty

from dad_player.constants import REPEAT_NONE, REPEAT_SONG, REPEAT_PLAYLIST, REPEAT_MODES_TEXT

class PlayerEngine(EventDispatcher):
    """
    Handles audio playback using python-vlc.
    Emits events for state changes, song end, position updates, and playlist changes.
    """
    __events__ = (
        'on_playback_started', 'on_playback_paused', 'on_playback_resumed',
        'on_playback_stopped', 'on_playback_finished', 'on_position_changed',
        'on_media_loaded', 'on_error', 'on_status_update', 'on_playlist_changed',
        'on_shuffle_mode_changed', 'on_repeat_mode_changed', 'on_volume_changed'
    )

    current_song = ObjectProperty(None, allownone=True)

    def __init__(self, settings_manager=None, **kwargs):
        super().__init__(**kwargs)
        
        if settings_manager is None:
            Logger.warning("PlayerEngine: Initialized WITHOUT a settings_manager instance!")
        else:
            Logger.info("PlayerEngine: Initialized WITH a settings_manager instance.")
        self.settings_manager = settings_manager 

        try:
            instance_args = ["--no-video", "--quiet", "--no-metadata-network-access", "--no-interact"]
            self.vlc_instance = vlc.Instance(" ".join(instance_args))
            self.player = self.vlc_instance.media_player_new()
        except Exception as e:
            Logger.critical(f"PlayerEngine: Failed to initialize VLC instance or player: {e}")
            self.vlc_instance = None
            self.player = None
            raise RuntimeError(f"VLC initialization failed: {e}. Is VLC installed and in PATH?")

        self.current_media_path = None
        self.current_media_duration_ms = 0
        self._is_playing_internal = False
        self._is_paused_internal = False
        self._was_paused_before_play = False

        self._volume = 100
        if self.player:
            self.set_volume(self._volume, dispatch_event=False)

        # VLC Event Manager
        if self.player:
            self.event_manager = self.player.event_manager()
            self.event_manager.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_vlc_playing)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerPaused, self._on_vlc_paused)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerStopped, self._on_vlc_stopped)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached)
            self.event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
            # MediaParsedChanged can be useful for getting duration.
            # We can also use MediaPlayerMediaChanged to know when new media is set.
            # For duration, we'll try to get it when playing starts or with a slight delay.
        else:
            self.event_manager = None


        self._position_update_event = None # Kivy Clock event for position updates

        # Playlist related attributes
        self._playlist = [] # List of file paths
        self._playlist_metadata = {} # Cache for metadata of playlist items
        self._shuffled_playlist = [] # Shuffled version of the playlist
        self._current_playlist_index = -1 # Index in the *active* playlist (shuffled or normal)
        
        # Load settings if settings_manager is available
        if self.settings_manager:
            self.shuffle_mode = self.settings_manager.get_shuffle()
            self.repeat_mode = self.settings_manager.get_repeat_mode()
            self.autoplay_mode = self.settings_manager.get_autoplay()
        else: # Defaults if no settings_manager
            self.shuffle_mode = False
            self.repeat_mode = REPEAT_NONE 
            self.autoplay_mode = True

    # --- Default Kivy Event Handlers (stubs for user to connect to) ---
    def on_playback_started(self, media_path): Logger.debug(f"Event: on_playback_started for {media_path}")
    def on_playback_paused(self, media_path): Logger.debug(f"Event: on_playback_paused for {media_path}")
    def on_playback_resumed(self, media_path): Logger.debug(f"Event: on_playback_resumed for {media_path}")
    def on_playback_stopped(self, media_path): Logger.debug(f"Event: on_playback_stopped for {media_path}")
    def on_playback_finished(self, media_path): Logger.debug(f"Event: on_playback_finished for {media_path}")
    def on_position_changed(self, position_ms, duration_ms): Logger.trace(f"Event: on_position_changed {position_ms}/{duration_ms}") 
    def on_media_loaded(self, media_path, duration_ms): Logger.debug(f"Event: on_media_loaded {media_path}, duration {duration_ms}ms")
    def on_error(self, error_message): Logger.error(f"Event: on_error: {error_message}")
    def on_status_update(self, status_message): Logger.info(f"Event: on_status_update: {status_message}")
    def on_playlist_changed(self, playlist_details_list): Logger.debug(f"Event: on_playlist_changed, {len(playlist_details_list)} items")
    def on_shuffle_mode_changed(self, shuffle_state_bool): Logger.debug(f"Event: on_shuffle_mode_changed to {shuffle_state_bool}")
    def on_repeat_mode_changed(self, repeat_mode_int): Logger.debug(f"Event: on_repeat_mode_changed to {repeat_mode_int}")
    def on_volume_changed(self, volume_float_0_1): Logger.debug(f"Event: on_volume_changed to {volume_float_0_1}")
    # --- End Default Kivy Event Handlers ---

    def _schedule_dispatch(self, event_name, *args):
        """Helper to schedule event dispatching on Kivy's main thread."""
        Clock.schedule_once(lambda dt: self.dispatch(event_name, *args), 0)

    # --- VLC Event Callbacks (prefixed with _on_vlc_ to distinguish) ---
    def _on_vlc_playing(self, event):
        Logger.info("PlayerEngine: VLC event - Playing")
        self._is_playing_internal = True
        self._is_paused_internal = False
        
        # Try to update duration if it wasn't available before
        if self.player and self.current_media_duration_ms <= 0:
            media = self.player.get_media()
            if media:
                duration = media.get_duration()
                if duration > 0:
                    self.current_media_duration_ms = duration
                    Logger.info(f"PlayerEngine: Duration updated on playing: {duration}ms for {self.current_media_path}")
                    self._schedule_dispatch('on_media_loaded', self.current_media_path, self.current_media_duration_ms)

        self._start_position_updater() 
        if self._was_paused_before_play:
            self._schedule_dispatch('on_playback_resumed', self.current_media_path)
            self._was_paused_before_play = False 
        else:
            self._schedule_dispatch('on_playback_started', self.current_media_path)
        self._schedule_dispatch('on_status_update', f"Playing: {os.path.basename(self.current_media_path or 'Unknown')}")

    def _on_vlc_paused(self, event):
        Logger.info("PlayerEngine: VLC event - Paused")
        self._is_playing_internal = False 
        self._is_paused_internal = True
        self._was_paused_before_play = True 
        self._schedule_dispatch('on_playback_paused', self.current_media_path)
        self._schedule_dispatch('on_status_update', "Paused")

    def _on_vlc_stopped(self, event):
        state = self.player.get_state() if self.player else None
        Logger.info(f"PlayerEngine: VLC event - Stopped (Current VLC State: {state})")

        if state not in [vlc.State.Ended, vlc.State.Error, vlc.State.NothingSpecial, vlc.State.Opening, None]: 
            self._is_playing_internal = False
            self._is_paused_internal = False
            self._stop_position_updater()
            self._schedule_dispatch('on_playback_stopped', self.current_media_path)
            self._schedule_dispatch('on_status_update', "Stopped")
            self.current_media_duration_ms = 0 
            self._schedule_dispatch('on_position_changed', 0, 0) 

    def _on_vlc_end_reached(self, event):
        Logger.info("PlayerEngine: VLC event - EndReached")
        self._is_playing_internal = False
        self._is_paused_internal = False
        self._stop_position_updater()
        
        finished_path = self.current_media_path 
        
        self._schedule_dispatch('on_playback_finished', finished_path)
        self._schedule_dispatch('on_status_update', "Finished")
        if self.current_media_duration_ms > 0 : 
             self._schedule_dispatch('on_position_changed', self.current_media_duration_ms, self.current_media_duration_ms)

        if self.autoplay_mode:
            Clock.schedule_once(lambda dt: self.play_next(from_song_end=True), 0.1) 

    def _on_vlc_error(self, event):
        Logger.error("PlayerEngine: VLC event - Error Encountered")
        self._is_playing_internal = False
        self._is_paused_internal = False
        self._stop_position_updater()
        self._schedule_dispatch('on_error', f"VLC playback error for {self.current_media_path}")
        self._schedule_dispatch('on_status_update', "Error")

    # --- Kivy Clock based Position Updater ---
    def _start_position_updater(self):
        self._stop_position_updater() 
        self._position_update_event = Clock.schedule_interval(self._update_position_regularly, 0.25)

    def _stop_position_updater(self):
        if self._position_update_event:
            self._position_update_event.cancel()
            self._position_update_event = None

    def _update_position_regularly(self, dt):
        if self.player and (self.is_playing() or self.is_paused()): 
            pos_ms = self.player.get_time() 

            if self.player: 
                current_media_obj = self.player.get_media()
                if current_media_obj: 
                    duration_check = current_media_obj.get_duration()
                    if duration_check > 0 and duration_check != self.current_media_duration_ms:
                        self.current_media_duration_ms = duration_check
                        # Dispatch on_media_loaded again if duration was unknown and now is known
                        self._schedule_dispatch('on_media_loaded', self.current_media_path, self.current_media_duration_ms)
                
                if pos_ms >= 0 and self.current_media_duration_ms > 0: 
                    self.dispatch('on_position_changed', pos_ms, self.current_media_duration_ms)
                elif pos_ms == -1 and self.current_media_duration_ms > 0: 
                     self.dispatch('on_position_changed', self.current_media_duration_ms, self.current_media_duration_ms)

    # --- Public Playback Control Methods ---
    def load_media(self, file_path, play_immediately=False):
        if not self.player:
            self._schedule_dispatch('on_error', "VLC Player not initialized.")
            return False
        if not file_path or not os.path.exists(file_path): 
            self._schedule_dispatch('on_error', f"File not found or invalid path: {file_path}")
            return False

        self.stop() 
        self.current_media_path = file_path
        Logger.info(f"PlayerEngine: Setting current_song to {file_path}")
        self.current_song = file_path 

        app = App.get_running_app()
        track_metadata = None
        if app and hasattr(app, 'library_manager') and app.library_manager:
            track_metadata = app.library_manager.get_track_details_by_filepath(file_path) 
        
        self._playlist_metadata[file_path] = track_metadata or {
            'filepath': file_path, 'title': os.path.splitext(os.path.basename(file_path))[0],
            'artist': "Unknown Artist", 'album': "Unknown Album", 'duration': 0 
        }

        abs_file_path = os.path.abspath(file_path)
        
        media = self.vlc_instance.media_new_path(abs_file_path)
        if not media:
            self._schedule_dispatch('on_error', f"VLC failed to create media for path: {abs_file_path}")
            return False
        
        self.player.set_media(media)
        media.release() 


        self.current_media_duration_ms = 0 # Assume 0 initially
        Clock.schedule_once(self._fetch_initial_duration, 0.2) # MODIFIED: Increased delay slightly

        Logger.info(f"PlayerEngine: Loading media: {file_path}. Will fetch duration shortly.")
        # Dispatch on_media_loaded with initial (possibly 0) duration. 
        # It will be dispatched again in _fetch_initial_duration or _on_vlc_playing if duration is found.
        self._schedule_dispatch('on_media_loaded', self.current_media_path, self.current_media_duration_ms)
        self._schedule_dispatch('on_status_update', f"Loaded: {os.path.basename(file_path)}")

        if play_immediately:
            self.play()
        return True

    def _fetch_initial_duration(self, dt):
        """Helper to fetch duration after a short delay, giving VLC time to parse."""
        if self.player:
            media = self.player.get_media()
            if media:
                duration = media.get_duration()
                if duration > 0:
                    if self.current_media_duration_ms != duration:
                        self.current_media_duration_ms = duration
                        Logger.info(f"PlayerEngine: Fetched initial duration (delayed): {self.current_media_duration_ms}ms for {self.current_media_path}")
                        self._schedule_dispatch('on_media_loaded', self.current_media_path, self.current_media_duration_ms)
                else:
                    Logger.warning(f"PlayerEngine: Still no valid duration after delay for {self.current_media_path}. Will try on play.")
            else:
                Logger.warning(f"PlayerEngine: No media object found in _fetch_initial_duration for {self.current_media_path}")
        else:
            Logger.warning("PlayerEngine: Player not available in _fetch_initial_duration.")


    def play(self):
        if self.player and self.current_media_path:
            if self.player.play() == -1: 
                self._schedule_dispatch('on_error', "Failed to start playback.")
                return False
            return True
        self._schedule_dispatch('on_error', "No media loaded to play.")
        return False

    def pause(self):
        if self.player and self.is_playing(): 
            self.player.pause() 
            return True
        return False

    def resume(self):
        if self.player and self.is_paused(): 
            self.player.pause() 
            return True
        return False
        
    def play_pause_toggle(self):
        if not self.player or not self.current_media_path:
            self._schedule_dispatch('on_error', "No media loaded.")
            return

        if self.is_playing():
            self.pause()
        elif self.is_paused():
            self.resume()
        else: 
            self.play()

    def stop(self):
        if self.player:
            self.player.stop() 
            return True
        return False

    def seek(self, position_ms):
        if self.player and self.current_media_path and self.current_media_duration_ms > 0:
            position_ms = max(0, min(int(position_ms), self.current_media_duration_ms))
            self.player.set_time(int(position_ms))
            self._schedule_dispatch('on_position_changed', int(position_ms), self.current_media_duration_ms)
            self._schedule_dispatch('on_status_update', f"Seeked to {position_ms / 1000:.1f}s")
            return True
        return False

    def set_volume(self, volume_0_to_100, dispatch_event=True):
        if self.player:
            self._volume = max(0, min(100, int(volume_0_to_100)))
            self.player.audio_set_volume(self._volume)
            if dispatch_event:
                self._schedule_dispatch('on_volume_changed', self._volume / 100.0) 
            return True
        return False

    def get_volume(self):
        return self._volume 

    # --- State Info ---
    def get_current_position_ms(self):
        return self.player.get_time() if self.player and self.current_media_path else 0

    def get_current_duration_ms(self):
        if self.player and self.current_media_duration_ms <= 0:
            media = self.player.get_media()
            if media:
                duration = media.get_duration()
                if duration > 0:
                    self.current_media_duration_ms = duration
        return self.current_media_duration_ms

    def is_playing(self):
        return self._is_playing_internal 

    def is_paused(self):
        return self._is_paused_internal 

    # --- Playlist Management ---
    def _get_active_playlist(self):
        return self._shuffled_playlist if self.shuffle_mode and self._shuffled_playlist else self._playlist

    def load_playlist(self, filepaths, play_index=0, clear_current=True):
        if clear_current:
            self.clear_playlist(dispatch_event=False) 

        app = App.get_running_app() 
        temp_playlist = []
        for path in filepaths:
            if not os.path.exists(path):
                Logger.warning(f"PlayerEngine: File not found in load_playlist: {path}")
                continue
            temp_playlist.append(path)
            if path not in self._playlist_metadata and app and hasattr(app, 'library_manager') and app.library_manager:
                meta = app.library_manager.get_track_details_by_filepath(path)
                self._playlist_metadata[path] = meta or {'filepath': path, 'title': os.path.basename(path), 'artist': 'Unknown', 'duration': 0}
        
        self._playlist = temp_playlist 
        
        if self.shuffle_mode:
            self._shuffled_playlist = list(self._playlist) 
            random.shuffle(self._shuffled_playlist)
        
        self._schedule_dispatch('on_playlist_changed', self.get_current_playlist_details())
        
        active_list = self._get_active_playlist()
        if play_index is not None and 0 <= play_index < len(active_list):
            self.play_from_playlist_by_index(play_index)
        elif active_list: 
            self.play_from_playlist_by_index(0)

    def add_to_playlist(self, filepaths):
        if isinstance(filepaths, str): filepaths = [filepaths] 

        app = App.get_running_app()
        added_paths = []
        for path in filepaths:
            if not os.path.exists(path):
                Logger.warning(f"PlayerEngine: File not found in add_to_playlist: {path}")
                continue
            added_paths.append(path)
            if path not in self._playlist_metadata and app and hasattr(app, 'library_manager') and app.library_manager:
                 meta = app.library_manager.get_track_details_by_filepath(path)
                 self._playlist_metadata[path] = meta or {'filepath': path, 'title': os.path.basename(path), 'artist': 'Unknown', 'duration': 0}
        
        if not added_paths: return

        self._playlist.extend(added_paths)
        
        if self.shuffle_mode: 
            self._shuffled_playlist = list(self._playlist)
            random.shuffle(self._shuffled_playlist)
            if self.current_media_path and self.current_media_path in self._shuffled_playlist:
                try: self._current_playlist_index = self._shuffled_playlist.index(self.current_media_path)
                except ValueError: self._current_playlist_index = 0 if self._shuffled_playlist else -1
            elif self._shuffled_playlist: self._current_playlist_index = 0 
            else: self._current_playlist_index = -1
        elif self._current_playlist_index == -1 and self._playlist: 
            self._current_playlist_index = 0
            
        self._schedule_dispatch('on_playlist_changed', self.get_current_playlist_details())
        
        if not self.is_playing() and not self.is_paused() and len(self._get_active_playlist()) == len(added_paths):
             self.play_from_playlist_by_index(0) 


    def clear_playlist(self, dispatch_event=True):
        self.stop() 
        self._playlist = []
        self._shuffled_playlist = []
        self._playlist_metadata = {} 
        self.current_media_path = None 
        self.current_media_duration_ms = 0
        self.current_song = None 
        self._current_playlist_index = -1
        if dispatch_event:
            self._schedule_dispatch('on_playlist_changed', []) 
            self._schedule_dispatch('on_status_update', "Playlist cleared")
            self._schedule_dispatch('on_media_loaded', None, 0) 
            self._schedule_dispatch('on_position_changed',0,0)


    def play_from_playlist_by_index(self, index):
        active_list = self._get_active_playlist()
        if 0 <= index < len(active_list):
            self._current_playlist_index = index
            filepath_to_play = active_list[index]
            Logger.info(f"PlayerEngine: Playing from playlist index {index}, path: {filepath_to_play}")
            return self.load_media(filepath_to_play, play_immediately=True)
        Logger.warning(f"PlayerEngine: Invalid playlist index: {index} for list size {len(active_list)}")
        return False

    def get_current_playlist_details(self):
        details = []
        active_list = self._get_active_playlist()
        for path in active_list:
            meta = self._playlist_metadata.get(path, {'filepath': path, 'title': os.path.basename(path), 'artist': 'Unknown', 'duration': 0})
            details.append(meta)
        return details

    def set_shuffle_mode(self, shuffle_on: bool):
        if self.shuffle_mode == shuffle_on: return 
        self.shuffle_mode = shuffle_on
        
        current_playing_path = self.current_media_path 
        
        if self.shuffle_mode:
            self._shuffled_playlist = list(self._playlist)
            random.shuffle(self._shuffled_playlist)
            if current_playing_path and current_playing_path in self._shuffled_playlist:
                self._current_playlist_index = self._shuffled_playlist.index(current_playing_path)
            elif self._shuffled_playlist: self._current_playlist_index = 0 
            else: self._current_playlist_index = -1
        else: 
            self._shuffled_playlist = [] 
            if current_playing_path and current_playing_path in self._playlist:
                self._current_playlist_index = self._playlist.index(current_playing_path)
            elif self._playlist: self._current_playlist_index = 0 
            else: self._current_playlist_index = -1
            
        self._schedule_dispatch('on_shuffle_mode_changed', self.shuffle_mode)
        self._schedule_dispatch('on_playlist_changed', self.get_current_playlist_details()) 
        self._schedule_dispatch('on_status_update', f"Shuffle {'On' if self.shuffle_mode else 'Off'}")

    def set_repeat_mode(self, mode: int):
        if mode in [REPEAT_NONE, REPEAT_SONG, REPEAT_PLAYLIST]:
            if self.repeat_mode == mode: return 
            self.repeat_mode = mode
            self._schedule_dispatch('on_repeat_mode_changed', self.repeat_mode)
            self._schedule_dispatch('on_status_update', f"Repeat: {REPEAT_MODES_TEXT.get(mode, 'Unknown')}")
        else:
            Logger.warning(f"PlayerEngine: Invalid repeat mode: {mode}")

    def set_autoplay_mode(self, autoplay_on: bool):
        if self.autoplay_mode == autoplay_on: return 
        self.autoplay_mode = autoplay_on
        self._schedule_dispatch('on_status_update', f"Autoplay Next {'On' if self.autoplay_mode else 'Off'}")

    def play_next(self, from_song_end=False): 
        active_list = self._get_active_playlist()
        if not active_list:
            self._schedule_dispatch('on_status_update', "Playlist empty. Cannot play next.")
            return False

        if self.repeat_mode == REPEAT_SONG and from_song_end: 
            if self.current_media_path:
                Logger.info("PlayerEngine: Repeating current song (from song end).")
                return self.load_media(self.current_media_path, play_immediately=True)
            return False 

        new_index = self._current_playlist_index + 1
        if new_index >= len(active_list): 
            if self.repeat_mode == REPEAT_PLAYLIST:
                new_index = 0 
            else: 
                self._schedule_dispatch('on_status_update', "End of playlist.")
                self.stop() 
                return False
        
        return self.play_from_playlist_by_index(new_index)

    def play_previous(self):
        active_list = self._get_active_playlist()
        if not active_list:
            self._schedule_dispatch('on_status_update', "Playlist empty. Cannot play previous.")
            return False

        if self.get_current_position_ms() > 3000 and self.current_media_path: 
             Logger.info("PlayerEngine: Restarting current song on previous (played >3s).")
             return self.load_media(self.current_media_path, play_immediately=True)

        if self.repeat_mode == REPEAT_SONG: 
            if self.current_media_path:
                Logger.info("PlayerEngine: Repeating current song on previous (repeat_song mode).")
                return self.load_media(self.current_media_path, play_immediately=True)
            return False

        new_index = self._current_playlist_index - 1
        if new_index < 0: 
            if self.repeat_mode == REPEAT_PLAYLIST:
                new_index = len(active_list) - 1 if active_list else -1 
            else: 
                new_index = 0 
        
        if new_index == -1 and not active_list : return False 
        
        return self.play_from_playlist_by_index(new_index)


    def _get_raw_art_for_current_track(self):
        if self.current_media_path:
            try:
                audio_file = mutagen.File(self.current_media_path, easy=False) 
                if audio_file:
                    if 'APIC:' in audio_file: 
                        return audio_file['APIC:'].data
                    elif 'covr' in audio_file and hasattr(audio_file['covr'][0], 'data'): 
                         return audio_file['covr'][0].data
                    elif hasattr(audio_file, 'pictures') and audio_file.pictures: 
                        return audio_file.pictures[0].data
                    elif 'metadata_block_picture' in audio_file: 
                        import base64
                        pic_data_b64_list = audio_file.get('metadata_block_picture')
                        if pic_data_b64_list:
                            pic_data_b64 = pic_data_b64_list[0]
                            if isinstance(pic_data_b64, str):
                                return base64.b64decode(pic_data_b64.split('|')[-1])
                            elif isinstance(pic_data_b64, bytes): 
                                return pic_data_b64
            except Exception as e:
                Logger.debug(f"PlayerEngine: Failed to get raw art for {self.current_media_path}: {e}")
        return None

    def shutdown(self):
        Logger.info("PlayerEngine: Shutting down...")
        self._stop_position_updater() 
        if self.player:
            self.player.stop()
            if self.event_manager:
                try: 
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerPlaying)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerPaused)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerStopped)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerEndReached)
                    self.event_manager.event_detach(vlc.EventType.MediaPlayerEncounteredError)
                except Exception as e: 
                    Logger.warning(f"PlayerEngine: Error detaching VLC events: {e}")
            self.player.release()
            self.player = None
        if self.vlc_instance:
            self.vlc_instance.release()
            self.vlc_instance = None
        Logger.info("PlayerEngine: Shutdown complete.")

    def _bind_player_engine_events(self):
        if not self.player_engine:
            Logger.error("NowPlayingView: Cannot bind events, PlayerEngine is None")
            return
        Logger.info("NowPlayingView: Binding PlayerEngine events")
        self.player_engine.bind(
            on_playback_started=self._on_playback_state_changed,
            on_playback_stopped=self._on_playback_state_changed,
            on_playback_paused=self._on_playback_state_changed,
            on_playback_resumed=self._on_playback_state_changed,
            on_media_loaded=self._on_media_loaded,
            on_position_changed=self._on_position_changed,
            on_error=self._on_player_error,
            on_shuffle_mode_changed=self._on_shuffle_mode_changed,
            on_repeat_mode_changed=self._on_repeat_mode_changed
        )

