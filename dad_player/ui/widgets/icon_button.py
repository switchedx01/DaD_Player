# dad_player/ui/widgets/icon_button.py
from kivy.uix.button import Button
from kivy.properties import StringProperty, ListProperty, NumericProperty
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import sp # Import Kivy's sp metric

# from dad_player.utils import spx # No longer using spx from utils here

class IconButton(Button):
    icon_text = StringProperty('')
    circle_color_normal = ListProperty([0.28, 0.28, 0.28, 1])
    circle_color_down = ListProperty([0.4, 0.4, 0.4, 1])
    icon_color_normal = ListProperty([0.9, 0.9, 0.9, 1])
    icon_color_down = ListProperty([0.95, 0.95, 0.95, 1])
    icon_font_name = StringProperty("Roboto")
    # Renamed to reflect it should be an sp value now, or handled as a direct pixel value if sp() is applied
    icon_font_size_sp = NumericProperty(sp(16)) # Default to sp(16)

    _current_circle_color = ListProperty([0,0,0,0])
    _current_icon_color = ListProperty([0,0,0,0])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = [0, 0, 0, 0] # Transparent background for custom drawing

        self._current_circle_color = self.circle_color_normal
        self._current_icon_color = self.icon_color_normal
        
        self.bind(
            icon_text=self._update_text_and_font, # Combined update
            icon_font_size_sp=self._update_text_and_font, # Combined update
            icon_font_name=self.setter('font_name'), # Directly set Button's font_name
            circle_color_normal=self._update_colors_from_normal,
            icon_color_normal=self._update_colors_from_normal,
            pos=self._redraw_canvas,
            size=self._redraw_canvas,
            state=self._on_state_change
        )
        
        self._update_text_and_font() # Initial setup for text, font_size
        # self.draw_custom_graphics() # Initial draw, or let pos/size binding handle it
        Clock.schedule_once(self.draw_custom_graphics, 0.01) # Ensure layout has settled

    def _update_text_and_font(self, *args):
        self.text = self.icon_text         # Set Button's text to the icon character
        self.font_size = self.icon_font_size_sp # Directly use the sp value for Button's font_size
        # self.texture_update() # Usually not needed to call manually, Kivy handles it
        Logger.trace(f"IconButton: Text set to '{self.text}', Font size set to {self.font_size}")


    def _update_colors_from_normal(self, *args):
        if self.state == 'normal':
            self._current_circle_color = self.circle_color_normal
            self._current_icon_color = self.icon_color_normal
            self.color = self._current_icon_color # Set Button's text color
            self._redraw_canvas()

    def _on_state_change(self, instance, value):
        if value == 'down':
            self._current_circle_color = self.circle_color_down
            self._current_icon_color = self.icon_color_down
        else: # 'normal'
            self._current_circle_color = self.circle_color_normal
            self._current_icon_color = self.icon_color_normal
        
        self.color = self._current_icon_color # Update Button's text color
        self._redraw_canvas()

    def _redraw_canvas(self, *args):
        # Schedule for next frame to ensure all properties (like size/pos) are updated
        Clock.schedule_once(self.draw_custom_graphics, -1) 

    def draw_custom_graphics(self, *args):
        if not self.canvas or self.width <= 1 or self.height <= 1:
            # Logger.trace("IconButton: Canvas not ready or size too small for drawing.")
            return

        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._current_circle_color)
            diameter = min(self.width, self.height) * 0.9 
            ellipse_x = self.center_x - diameter / 2
            ellipse_y = self.center_y - diameter / 2
            Ellipse(pos=(ellipse_x, ellipse_y), size=(diameter, diameter))
        
        # The Button's text (icon) will be drawn by the Button itself using self.color.
        # self.color = self._current_icon_color # Already set in _on_state_change

class IconOnlyButton(IconButton): # Example of a variant if needed
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Example: Different default colors or font size for this specific type
        # self.icon_font_size_sp = sp(20) 
