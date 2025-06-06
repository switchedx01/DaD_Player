# dad_player/ui/widgets/song_list_item.py
import os
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ObjectProperty, NumericProperty, BooleanProperty
from kivy.logger import Logger
from kivy.app import App
from kivy.metrics import dp, sp
from dad_player.utils import format_duration

class SongListItem(BoxLayout):
    track_id = NumericProperty(None)
    track_number_text = StringProperty("")
    song_title_text = StringProperty("Unknown Title")
    artist_name_text = StringProperty("Unknown Artist")
    duration_text = StringProperty("00:00")
    art_path = StringProperty(None)
    is_playing = BooleanProperty(False)
    on_press_callback = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.art_path or not os.path.exists(self.art_path):
            app = App.get_running_app()
            if app and hasattr(app, 'icons_dir'):
                 from dad_player.core.image_utils import get_placeholder_album_art_path
                 self.art_path = get_placeholder_album_art_path(app.icons_dir)
        Logger.debug(f"SongListItem [INIT]: Title: '{self.song_title_text}', Art: '{self.art_path}'")


    def on_art_path(self, instance, path):
        if self.ids.get('song_item_art_image'):
            if path and os.path.exists(path):
                self.ids.song_item_art_image.source = path
                self.ids.song_item_art_image.reload()
            else:
                app = App.get_running_app()
                if app and hasattr(app, 'icons_dir'):
                    from dad_player.core.image_utils import get_placeholder_album_art_path
                    placeholder = get_placeholder_album_art_path(app.icons_dir)
                    self.ids.song_item_art_image.source = placeholder if placeholder else ""
                    self.ids.song_item_art_image.reload()
                else:
                    self.ids.song_item_art_image.source = ''
        Logger.trace(f"SongListItem [on_art_path]: Path set to '{path}' for song '{self.song_title_text}'")


    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            if self.collide_point(*touch.pos) and self.on_press_callback:
                Logger.info(f"SongListItem [ON_TOUCH_UP]: Clicked on Track ID: {self.track_id}, Title: '{self.song_title_text}'")
                try:
                    self.on_press_callback()
                except Exception as e:
                    Logger.error(f"SongListItem [CALLBACK ERROR]: {e}", exc_info=True)

            return True
        return super().on_touch_up(touch)

    def update_data(self, data_dict):
        self.track_id = data_dict.get('track_id')
        track_num = data_dict.get('track_number')
        self.track_number_text = f"{track_num:02d}." if isinstance(track_num, int) and track_num > 0 else ""
        self.song_title_text = data_dict.get('title', "Unknown Title")
        self.artist_name_text = data_dict.get('artist_name', "Unknown Artist")
        duration_sec = data_dict.get('duration', 0)
        self.duration_text = format_duration(duration_sec)
        
        final_art_path = None
        new_art_path = data_dict.get('art_path')
        if new_art_path and os.path.exists(new_art_path):
            final_art_path = new_art_path
        else:
            app = App.get_running_app()
            if app and hasattr(app, 'icons_dir'):
                from dad_player.core.image_utils import get_placeholder_album_art_path
                final_art_path = get_placeholder_album_art_path(app.icons_dir)
        self.art_path = final_art_path

        Logger.debug(f"SongListItem [update_data]: Updated with Title: '{self.song_title_text}'")
