# dad_player/ui/widgets/artist_list_item.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.behaviors import ButtonBehavior
from kivy.properties import StringProperty, NumericProperty, ObjectProperty
from kivy.logger import Logger
from kivy.metrics import sp, dp 
    
class ArtistListItem(ButtonBehavior, BoxLayout):
        artist_id = NumericProperty(None)
        artist_name = StringProperty("Unknown Artist")
        on_press_callback = ObjectProperty(None, allownone=True)
    
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.orientation = 'horizontal'
            self.padding = [dp(10), dp(5)] 
            self.spacing = dp(10)        
            self.size_hint_y = None
            self.height = dp(48)         
    
            self.name_label = Label(
                text=self.artist_name,
                font_size=sp(15),        
                halign='left',
                valign='middle', 
                size_hint_x=1,
                color=[1, 1, 1, 1]
            )
            self.name_label.bind(size=self._update_label_text_size)
            self.add_widget(self.name_label)
    
            self.bind(artist_name=self._update_label_text)
            # Logger.debug(f"ArtistListItem [INIT]: ID: {self.artist_id}, Name: '{self.artist_name}'. Callback set: {self.on_press_callback is not None}")
    
        def _update_label_text_size(self, instance, size):
            instance.text_size = (size[0], None) 
    
        def _update_label_text(self, instance, value):
            if hasattr(self, 'name_label'):
                self.name_label.text = value
    
        def on_artist_name(self, instance, value):
            self._update_label_text(instance, value) 
    
        def on_on_press_callback(self, instance, value):
            Logger.critical(f"ArtistListItem [on_on_press_callback EVENT]: ID: {self.artist_id}, Name: '{self.artist_name}'. Callback (re)assigned: {value is not None}")
    
        def on_touch_down(self, touch):
            if self.disabled: 
                return False
            if self.collide_point(*touch.pos):
                # Logger.error(f"ArtistListItem [>>> RAW TOUCH DOWN INSIDE ITEM]: '{self.artist_name}' (ID: {self.artist_id}) at {touch.pos}. Grabbed: {touch.grab_current == self}")
                return super().on_touch_down(touch) 
            return super().on_touch_down(touch)
    
        def on_release(self): 
            Logger.critical(f"ArtistListItem [>>> ON_RELEASE]: '{self.artist_name}' (ID: {self.artist_id})")
            if callable(self.on_press_callback):
                Logger.critical(f"ArtistListItem [EXECUTING CALLBACK]: ID={self.artist_id}, Name='{self.artist_name}'.")
                try:
                    self.on_press_callback()
                except Exception as e:
                    Logger.error(f"ArtistListItem [CALLBACK ERROR]: {e}", exc_info=True)
            else:
                Logger.warning(f"ArtistListItem [NO CALLBACK]: '{self.artist_name}' (ID: {self.artist_id}). Callback was: {self.on_press_callback}")
    
