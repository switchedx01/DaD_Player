# dad_player/ui/screens/now_playing_view.py
print(f"Loading NowPlayingView from {__file__} - Version 1.5 with enhanced debugging")
import hashlib
import os
from io import BytesIO
from typing import Optional

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle
from kivy.logger import Logger
from kivy.properties import NumericProperty, ObjectProperty, StringProperty, BooleanProperty
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from PIL import Image, ImageFilter

from dad_player.constants import ALBUM_ART_NOW_PLAYING_SIZE, PLACEHOLDER_ALBUM_FILENAME, REPEAT_NONE, REPEAT_SONG, REPEAT_PLAYLIST, REPEAT_MODES_TEXT
from dad_player.core.player_engine import PlayerEngine
from dad_player.utils import format_duration
from dad_player.core.image_utils import resize_image_data, get_placeholder_album_art_path

class NowPlayingView(BoxLayout):
    player_engine = ObjectProperty(None)
    library_manager = ObjectProperty(None)

    current_time_text = StringProperty("0:00")
    total_time_text = StringProperty("0:00")
    song_title_text = StringProperty("No Track Loaded")
    artist_name_text = StringProperty("Unknown Artist")
    album_name_text = StringProperty("Unknown Album")
    progress_slider_value = NumericProperty(0)
    progress_slider_max = NumericProperty(1000)
    play_pause_icon_text = StringProperty("play-circle-outline") # KV maps this to emoji
    album_art_texture = ObjectProperty(None, allownone=True)
    blurred_bg_texture = ObjectProperty(None, allownone=True)
    shuffle_enabled = BooleanProperty(False)
    repeat_mode_icon = StringProperty("Repeat Off")

    _is_seeking = False
    _visual_debug_active = False

    def __init__(self, player_engine, library_manager, **kwargs):
        super().__init__(**kwargs)
        Logger.info(f"NowPlayingView [INIT]: Self: {self}, Size: {self.size}, Pos: {self.pos}, Parent: {self.parent}, Children: {self.children}, IDs: {self.ids}")

        self.player_engine = player_engine
        self.library_manager = library_manager

        Logger.info(f"NowPlayingView [INIT]: Initializing with PlayerEngine: {self.player_engine}, LibraryManager: {self.library_manager}")

        self._default_placeholder_texture = None
        self._default_blurred_placeholder_texture = None
        self._load_placeholder_textures()

        if self.player_engine:
            Logger.info("NowPlayingView [INIT]: Binding to PlayerEngine events")
            self.player_engine.bind(current_song=self._on_current_song_property_changed)
            self._bind_player_engine_custom_events()
            self.update_ui_from_player_state()
        else:
            Logger.error("NowPlayingView [INIT]: PlayerEngine is None, cannot bind events. Applying placeholder art.")
            self._apply_placeholder_art()

        Clock.schedule_once(self._check_initial_size, 0.1)
        Logger.info(f"NowPlayingView [INIT]: Initialization complete. Current Size: {self.size}, Pos: {self.pos}, Parent: {self.parent}")

    def _check_initial_size(self, dt):
        Logger.info(f"NowPlayingView [_check_initial_size]: Called. Current size: {self.size}, Pos: {self.pos}, Parent: {self.parent}")
        Logger.info(f"NowPlayingView [_check_initial_size]: Children: {self.children}")
        if self.parent:
            Logger.info(f"NowPlayingView [_check_initial_size]: Parent's children: {self.parent.children}")
        Logger.info(f"NowPlayingView [_check_initial_size]: IDs available: {bool(self.ids)}. Keys: {list(self.ids.keys()) if self.ids else 'None'}")
        if 'album_art_np' in self.ids:
            Logger.info(f"NowPlayingView [_check_initial_size]: album_art_np ID found: {self.ids['album_art_np']}")
        else:
            Logger.warning("NowPlayingView [_check_initial_size]: album_art_np ID NOT FOUND.")


    def on_size(self, instance, value):
        parent_info = f"Parent: {self.parent} (size: {self.parent.size if self.parent else 'N/A'})" if self.parent else "No parent assigned at on_size"
        ids_info = f"IDs available: {bool(self.ids)}"
        children_info = f"Children: {self.children}"
        if self.ids:
            ids_info += f" (Keys: {list(self.ids.keys())}, e.g., album_art_np exists: {'album_art_np' in self.ids})"
        else:
            ids_info += " (IDs dictionary is empty or None)"

        Logger.info(f"NowPlayingView [EVENT on_size]: Triggered. New size: {value}, Pos: {self.pos}. {parent_info}. {ids_info}. {children_info}")

        if self.parent and value[0] > 1 and value[1] > 1 and not self._visual_debug_active:
            Logger.info("NowPlayingView [EVENT on_size]: Applying VISUAL DEBUG background.")
            self._visual_debug_active = True
            with self.canvas.after:
                Color(0, 1, 0, 0.3)
                self.debug_rect = Rectangle(pos=self.pos, size=self.size)
            self.bind(pos=lambda i,p: setattr(self.debug_rect, 'pos', p),
                      size=lambda i,s: setattr(self.debug_rect, 'size', s))

            Clock.schedule_once(self._remove_visual_debug, 2)
        elif not self.parent:
            Logger.warning("NowPlayingView [EVENT on_size]: Cannot apply visual debug, no parent.")


    def _remove_visual_debug(self, dt):
        Logger.info("NowPlayingView [_remove_visual_debug]: Removing VISUAL DEBUG background.")
        if hasattr(self, 'debug_rect'):
            self.canvas.after.remove(self.debug_rect)
            del self.debug_rect
        self._visual_debug_active = False


    def _load_placeholder_textures(self):
        if self._default_placeholder_texture is None:
            app = App.get_running_app()
            if app and hasattr(app, 'icons_dir'):
                placeholder_path = get_placeholder_album_art_path(app.icons_dir)
                if placeholder_path and os.path.exists(placeholder_path):
                    try:
                        # Placeholder for main art
                        raw_placeholder_data = open(placeholder_path, 'rb').read()
                        resized_stream = resize_image_data(raw_placeholder_data, target_max_dim=ALBUM_ART_NOW_PLAYING_SIZE, output_format="PNG")
                        if resized_stream:
                            resized_stream.seek(0)
                            core_img = CoreImage(resized_stream, ext='png', mipmap=True, filename="placeholder_np.png")
                            self._default_placeholder_texture = core_img.texture
                            Logger.info("NowPlayingView [_load_placeholder_textures]: Loaded default placeholder texture.")

                        # Placeholder for blurred background
                        pil_for_blur = Image.open(BytesIO(raw_placeholder_data))
                        if pil_for_blur.mode == 'P': # Convert palettized images
                           pil_for_blur = pil_for_blur.convert('RGBA')
                        blurred_pil_img = pil_for_blur.filter(ImageFilter.GaussianBlur(25))
                        blurred_stream = BytesIO()
                        blurred_pil_img.save(blurred_stream, format='PNG')
                        blurred_stream.seek(0)
                        blurred_core_img = CoreImage(blurred_stream, ext='png', mipmap=True, filename="placeholder_blur_np.png")
                        self._default_blurred_placeholder_texture = blurred_core_img.texture
                        Logger.info("NowPlayingView [_load_placeholder_textures]: Loaded default blurred placeholder texture.")

                    except Exception as e:
                        Logger.error(f"NowPlayingView [_load_placeholder_textures]: Error loading placeholder textures: {e}")
                else:
                    Logger.error("NowPlayingView [_load_placeholder_textures]: Placeholder image path not found or app.icons_dir not available.")
            else:
                Logger.error("NowPlayingView [_load_placeholder_textures]: App instance or icons_dir not available for placeholder loading.")

    def _apply_placeholder_art(self):
        if self._default_placeholder_texture is None or self._default_blurred_placeholder_texture is None:
            self._load_placeholder_textures() # Attempt to load if not already loaded

        self.album_art_texture = self._default_placeholder_texture
        self.blurred_bg_texture = self._default_blurred_placeholder_texture
        Logger.debug("NowPlayingView [_apply_placeholder_art]: Applied placeholder art.")

    def _bind_player_engine_custom_events(self):
        if not self.player_engine:
            Logger.error("NowPlayingView [_bind_player_engine_custom_events]: Cannot bind events, PlayerEngine is None")
            return
        Logger.info("NowPlayingView [_bind_player_engine_custom_events]: Binding PlayerEngine custom events")
        self.player_engine.bind(
            on_playback_started=self._on_playback_state_changed,
            on_playback_stopped=self._on_playback_state_changed,
            on_playback_paused=self._on_playback_state_changed,
            on_playback_resumed=self._on_playback_state_changed,
            on_playback_finished=self._on_playback_finished,
            on_media_loaded=self._on_media_loaded,
            on_position_changed=self._on_position_changed,
            on_error=self._on_player_error,
            on_shuffle_mode_changed=self._on_shuffle_mode_changed,
            on_repeat_mode_changed=self._on_repeat_mode_changed,
            on_volume_changed=self._on_volume_changed
        )

    def _on_current_song_property_changed(self, instance, current_song_path):
        Logger.info(f"NowPlayingView [_on_current_song_property_changed]: PlayerEngine.current_song changed to: {current_song_path}")
        self.update_ui_from_player_state()

    def _on_playback_state_changed(self, instance, media_path_or_none=None):
        Logger.info(f"NowPlayingView [_on_playback_state_changed]: Playback state changed. Instance: {instance}, Path: {media_path_or_none}")
        self.update_ui_from_player_state()

    def _on_playback_finished(self, instance, finished_media_path):
        Logger.info(f"NowPlayingView [_on_playback_finished]: Playback finished for {finished_media_path}")
        self.update_ui_from_player_state()

    def _on_media_loaded(self, instance, media_path, duration_ms):
        Logger.info(f"NowPlayingView [_on_media_loaded]: Media loaded: {media_path}, Duration: {duration_ms}ms")
        self.update_ui_from_player_state()

    def _on_position_changed(self, instance, position_ms, duration_ms):
        if self.player_engine:
            self.current_time_text = format_duration(position_ms / 1000.0)
            if duration_ms > 0 :
                self.total_time_text = format_duration(duration_ms / 1000.0)
                self.progress_slider_max = duration_ms
            if not self._is_seeking:
                self.progress_slider_value = position_ms

    def _on_player_error(self, instance, error_message):
        Logger.error(f"NowPlayingView [_on_player_error]: Player error: {error_message}")
        self.song_title_text = "Error"
        self.artist_name_text = error_message
        self.album_name_text = "Please check logs"
        self._apply_placeholder_art()
        self.current_time_text = "0:00"
        self.total_time_text = "0:00"
        self.progress_slider_value = 0
        self.play_pause_icon_text = "play-circle-outline"

    def _on_shuffle_mode_changed(self, instance, shuffle_state_bool):
        Logger.info(f"NowPlayingView [_on_shuffle_mode_changed]: Shuffle mode changed to {shuffle_state_bool}")
        self.shuffle_enabled = shuffle_state_bool
        if hasattr(self, 'ids') and 'shuffle_button_np' in self.ids:
            self.ids.shuffle_button_np.text = "🔀" # Consider visual feedback like color change

    def _on_repeat_mode_changed(self, instance, repeat_mode_int):
        Logger.info(f"NowPlayingView [_on_repeat_mode_changed]: Repeat mode changed to {repeat_mode_int}")
        if repeat_mode_int == REPEAT_NONE:
            self.repeat_mode_icon = "Repeat Off"  # Or just "Repeat" and use button state for on/off
        elif repeat_mode_int == REPEAT_SONG:
            self.repeat_mode_icon = "Repeat Song"
        elif repeat_mode_int == REPEAT_PLAYLIST:
            self.repeat_mode_icon = "Repeat All" # Or "Repeat Playlist"
        else:
            self.repeat_mode_icon = "Repeat" # Default fallback
        Logger.debug(f"NowPlayingView [_on_repeat_mode_changed]: Set repeat_mode_icon to: {self.repeat_mode_icon}")



    def _on_volume_changed(self, instance, volume_float_0_1):
        Logger.info(f"NowPlayingView [_on_volume_changed]: Volume changed to {volume_float_0_1:.2f}")

    def update_ui_from_player_state(self, *args):
        Logger.info(f"NowPlayingView [update_ui_from_player_state]: Updating UI. PlayerEngine: {self.player_engine}")
        Logger.info(f"NowPlayingView [update_ui_from_player_state]: IDs available: {bool(self.ids)}. Keys: {list(self.ids.keys()) if self.ids else 'None'}")
        if 'album_art_np' not in self.ids:
            Logger.critical("NowPlayingView [update_ui_from_player_state]: 'album_art_np' ID NOT FOUND. UI will not update correctly.")

        if not self.player_engine:
            Logger.warning("NowPlayingView [update_ui_from_player_state]: PlayerEngine not available for UI update.")
            self._apply_placeholder_art()
            self.song_title_text = "Player Error"
            self.artist_name_text = "Engine not found"
            self.album_name_text = ""
            return

        current_track_path = self.player_engine.current_song
        Logger.info(f"NowPlayingView [update_ui_from_player_state]: Current track (from engine): {current_track_path}")

        if current_track_path and hasattr(self.player_engine, '_playlist_metadata') and self.player_engine._playlist_metadata:
            track_meta = self.player_engine._playlist_metadata.get(current_track_path, {})
            self.song_title_text = track_meta.get('title', os.path.splitext(os.path.basename(current_track_path))[0] if current_track_path else "No Track")
            self.artist_name_text = track_meta.get('artist', "Unknown Artist")
            self.album_name_text = track_meta.get('album', "Unknown Album")
            self.load_album_art_for_current_track()
            duration_ms = self.player_engine.get_current_duration_ms()
            self.total_time_text = format_duration(duration_ms / 1000.0) if duration_ms > 0 else "0:00"
            self.progress_slider_max = duration_ms if duration_ms > 0 else 1000
        else:
            Logger.info("NowPlayingView [update_ui_from_player_state]: No current track path or metadata, applying defaults.")
            self.song_title_text = "No Track Loaded"
            self.artist_name_text = "Unknown Artist"
            self.album_name_text = "Unknown Album"
            self._apply_placeholder_art()
            self.total_time_text = "0:00"
            self.progress_slider_max = 1000
            self.progress_slider_value = 0
            self.current_time_text = "0:00"

        if self.player_engine.is_playing():
            self.play_pause_icon_text = "pause-circle-outline"
        else:
            self.play_pause_icon_text = "play-circle-outline"

        current_pos_ms = self.player_engine.get_current_position_ms()
        self.current_time_text = format_duration(current_pos_ms / 1000.0)
        if not self._is_seeking:
            self.progress_slider_value = current_pos_ms

        self._on_shuffle_mode_changed(None, self.player_engine.shuffle_mode)
        self._on_repeat_mode_changed(None, self.player_engine.repeat_mode)
        Logger.info(f"NowPlayingView [update_ui_from_player_state]: UI properties updated - Song: {self.song_title_text}, Art Texture: {'Set' if self.album_art_texture else 'None'}")

    def load_album_art_for_current_track(self):
        Logger.debug(f"NowPlayingView [load_album_art_for_current_track]: Attempting to load art. Has PlayerEngine: {bool(self.player_engine)}. Current Song: {self.player_engine.current_song if self.player_engine else 'N/A'}")
        if not self.player_engine or not self.player_engine.current_song:
            Logger.debug("NowPlayingView [load_album_art_for_current_track]: No player engine or current_song. Applying placeholder.")
            self._apply_placeholder_art()
            return
        if self._default_placeholder_texture is None or self._default_blurred_placeholder_texture is None:
            self._load_placeholder_textures()

        raw_art_data = self.player_engine._get_raw_art_for_current_track() # Assumes PlayerEngine has this method
        if raw_art_data:
            try:
                resized_stream = resize_image_data(raw_art_data, target_max_dim=ALBUM_ART_NOW_PLAYING_SIZE, output_format="PNG")
                if resized_stream:
                    resized_stream.seek(0)
                    fn = f"np_art_{hashlib.md5(self.player_engine.current_song.encode()).hexdigest()}.png"
                    core_img = CoreImage(resized_stream, ext='png', mipmap=True, filename=fn)
                    self.album_art_texture = core_img.texture
                else: # resize_image_data failed
                    Logger.warning("NowPlayingView [load_album_art_for_current_track]: resize_image_data returned None for main art. Applying placeholder.")
                    self._apply_placeholder_art() # Apply placeholder for main art if resize fails
                    return # Don't try to blur if main art failed

                # Blurred background
                pil_for_blur = Image.open(BytesIO(raw_art_data)) # Use fresh BytesIO
                if pil_for_blur.mode == 'P':
                   pil_for_blur = pil_for_blur.convert('RGBA')
                blurred_pil_img = pil_for_blur.filter(ImageFilter.GaussianBlur(25))
                blurred_stream = BytesIO()
                blurred_pil_img.save(blurred_stream, format='PNG')
                blurred_stream.seek(0)
                fn_blur = f"np_blur_{hashlib.md5(self.player_engine.current_song.encode()).hexdigest()}.png"
                blurred_core_img = CoreImage(blurred_stream, ext='png', mipmap=True, filename=fn_blur)
                self.blurred_bg_texture = blurred_core_img.texture
                Logger.info("NowPlayingView [load_album_art_for_current_track]: Successfully loaded and blurred album art.")
                return
            except Exception as e:
                Logger.error(f"NowPlayingView [load_album_art_for_current_track]: Error processing album art for {self.player_engine.current_song}: {e}", exc_info=True)
                self._apply_placeholder_art() # Fallback to placeholder on any error
        else:
            Logger.debug(f"NowPlayingView [load_album_art_for_current_track]: No raw art data found for {self.player_engine.current_song}. Applying placeholder.")
            self._apply_placeholder_art()

    def on_progress_slider_touch_down(self, slider_instance):
        if self.player_engine and self.player_engine.current_song:
            self._is_seeking = True
            Logger.debug("NowPlayingView [SliderTouchDown]: _is_seeking = True")

    def on_progress_slider_touch_up(self, slider_instance):
        if self._is_seeking and self.player_engine and self.player_engine.current_song:
            target_ms = slider_instance.value
            Logger.debug(f"NowPlayingView [SliderTouchUp]: Seeking to {target_ms}ms. _is_seeking = False")
            self.player_engine.seek(target_ms)
            self.current_time_text = format_duration(target_ms / 1000.0)
        self._is_seeking = False

    def on_progress_slider_value_changed(self, slider_instance, value):
        if self._is_seeking:
            self.current_time_text = format_duration(value / 1000.0)

    def on_play_pause_button_press(self):
        if self.player_engine:
            self.player_engine.play_pause_toggle()

    def on_previous_button_press(self):
        if self.player_engine:
            self.player_engine.play_previous()

    def on_next_button_press(self):
        if self.player_engine:
            self.player_engine.play_next()

    def on_shuffle_button_press(self):
        if self.player_engine:
            new_shuffle_state = not self.player_engine.shuffle_mode
            self.player_engine.set_shuffle_mode(new_shuffle_state)

    def on_repeat_button_press(self):
        if self.player_engine and hasattr(self.player_engine, 'set_repeat_mode'):
            current_mode = self.player_engine.repeat_mode
            if current_mode == REPEAT_NONE:      next_mode = REPEAT_PLAYLIST
            elif current_mode == REPEAT_PLAYLIST: next_mode = REPEAT_SONG
            elif current_mode == REPEAT_SONG:    next_mode = REPEAT_NONE
            else:                                next_mode = REPEAT_NONE
            self.player_engine.set_repeat_mode(next_mode)

    def on_manage_folders_button_press(self):
        Logger.info("NowPlayingView: Manage folders button pressed (Placeholder - should be Settings button).")
        app = App.get_running_app()
        if app and hasattr(app, 'open_app_settings'):
            app.open_app_settings()
        else:
            Logger.warning("NowPlayingView: Could not open app settings (app or method not found).")

