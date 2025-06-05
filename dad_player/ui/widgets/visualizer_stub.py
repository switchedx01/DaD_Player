# dad_player/ui/widgets/visualizer_stub.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Line
from kivy.properties import ListProperty, NumericProperty, ObjectProperty # Added ObjectProperty
from kivy.clock import Clock
import numpy as np 

from dad_player.utils import spx

class VisualizerStub(BoxLayout):
    """
    A placeholder/stub for the audio visualizer.
    Can show dummy animated bars for now.
    """
    bars_data = ListProperty([0] * 20) 
    num_bars = NumericProperty(20)
    max_bar_height_val = NumericProperty(7) 
    player_engine = ObjectProperty(None, allownone=True) # To potentially get real data later

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal' 
        self.bar_colors = [
            (0.3,0.6,0.8,1),(0.4,0.7,0.9,1),(0.5,0.8,1.0,1),(0.6,0.9,0.9,1),
            (0.7,1.0,0.8,1),(0.8,0.9,0.7,1),(0.9,0.8,0.6,1),(1.0,0.7,0.5,1)
        ]
        self._anim_event = None
        self.bind(size=self._redraw_bars, pos=self._redraw_bars) 

    def start_dummy_animation(self):
        if not self._anim_event:
            self._anim_event = Clock.schedule_interval(self.update_dummy_bars, 1/20) 

    def stop_dummy_animation(self):
        if self._anim_event:
            self._anim_event.cancel()
            self._anim_event = None
        self.bars_data = [0] * self.num_bars 
        self._redraw_bars() # Explicitly call redraw after stopping


    def update_dummy_bars(self, dt):
        current_time = Clock.get_boottime()
        new_bars = []
        for i in range(self.num_bars):
            val = (np.sin(current_time * 3 + i * 0.5) + 1) / 2  
            new_bars.append(int(val * self.max_bar_height_val))
        self.bars_data = new_bars
        # self._redraw_bars() # on_bars_data will trigger this
        
    def on_player_engine(self, instance, value):
        # This method is called when the player_engine property is set or changes.
        if self.player_engine:
            if self.player_engine.is_playing(): # Check if player_engine indicates playing
                self.start_dummy_animation()
            else:
                self.stop_dummy_animation()
        else:
            self.stop_dummy_animation()


    def on_bars_data(self, instance, value):
        self._redraw_bars()

    def on_size(self, *args):
        self._redraw_bars()

    def on_pos(self, *args):
        self._redraw_bars()

    def _redraw_bars(self, *args):
        self.canvas.clear() # Use self.canvas.clear() for widgets
        if not self.bars_data or self.width <=0 or self.height <=0:
            return

        with self.canvas: # Use self.canvas for widgets
            bar_total_width = self.width / max(1, self.num_bars)
            spacing = bar_total_width * 0.15
            actual_bar_width = bar_total_width - spacing
            if actual_bar_width < 1: actual_bar_width = 1

            for i, val in enumerate(self.bars_data):
                if not isinstance(val, (int, float)): val = 0
                normalized_val = max(0, min(val, self.max_bar_height_val))
                
                bar_height_px = (normalized_val / self.max_bar_height_val) * self.height \
                                if self.max_bar_height_val > 0 else 0
                
                color_index = int(normalized_val) % len(self.bar_colors)
                Color(*self.bar_colors[color_index])
                
                # Corrected x_pos calculation relative to widget's self.x
                x_pos_offset = i * bar_total_width + (spacing / 2)
                Rectangle(pos=(self.x + x_pos_offset, self.y), size=(actual_bar_width, bar_height_px))

