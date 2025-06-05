# dad_player/ui/widgets/album_grid_item.py
import os
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, ObjectProperty, NumericProperty
from kivy.logger import Logger
from kivy.app import App
from kivy.metrics import dp, sp # Import Kivy's metrics

# from dad_player.utils import spx # REMOVED spx import

class AlbumGridItem(BoxLayout):
    album_id = NumericProperty(None)
    album_name = StringProperty("Unknown Album")
    artist_name = StringProperty("Unknown Artist")
    art_path = StringProperty(None)
    on_press_callback = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Sizing and internal element properties should be handled in KV with dp/sp.
        # This Python code should primarily focus on logic.
        if not self.art_path or not os.path.exists(self.art_path):
            app = App.get_running_app()
            if app and hasattr(app, 'icons_dir'):
                 from dad_player.core.image_utils import get_placeholder_album_art_path
                 self.art_path = get_placeholder_album_art_path(app.icons_dir)
        Logger.debug(f"AlbumGridItem [INIT]: Album: '{self.album_name}', Art: '{self.art_path}'")


    def on_art_path(self, instance, path):
        if self.ids.get('album_art_image'):
            if path and os.path.exists(path):
                self.ids.album_art_image.source = path
                self.ids.album_art_image.reload()
            else:
                app = App.get_running_app()
                if app and hasattr(app, 'icons_dir'):
                    from dad_player.core.image_utils import get_placeholder_album_art_path
                    placeholder = get_placeholder_album_art_path(app.icons_dir)
                    self.ids.album_art_image.source = placeholder if placeholder else ""
                    self.ids.album_art_image.reload()
                else:
                    self.ids.album_art_image.source = ''
        Logger.trace(f"AlbumGridItem [on_art_path]: Path set to '{path}' for album '{self.album_name}'")


    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            if self.collide_point(*touch.pos) and self.on_press_callback:
                Logger.info(f"AlbumGridItem [ON_TOUCH_UP]: Clicked on Album ID: {self.album_id}, Name: '{self.album_name}'")
                try:
                    self.on_press_callback()
                except Exception as e:
                    Logger.error(f"AlbumGridItem [CALLBACK ERROR]: {e}", exc_info=True)
            return True
        return super().on_touch_up(touch)
