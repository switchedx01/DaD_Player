from kivy.logger import Logger
import os
import sys
from kivy.config import Config
from kivy.clock import Clock
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button

Config.set('input', 'mouse', 'mouse,disable_multitouch')
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
Config.set('modules', 'inspector', '') # Ensures it's not disabled by an empty string


def test_import(module_name, class_name=None):
    """Tests importing a module and optionally a class within that module."""
    try:
        module = __import__(module_name, fromlist=[''])
        print(f"SUCCESS: Imported module '{module_name}'.")
        if class_name:
            try:
                class_obj = getattr(module, class_name)
                print(f"SUCCESS: Imported class '{class_name}' from '{module_name}'.")
            except AttributeError:
                print(f"ERROR: Class '{class_name}' not found in '{module_name}'.")
                return False
            except Exception as e:
                print(f"ERROR: Error importing class '{class_name}' from '{module_name}': {e}")
                return False
        return True
    except (ModuleNotFoundError, ImportError) as e:
        print(f"ERROR: Could not import module '{module_name}': {e}")
        return False
    except Exception as e:
        print(f"ERROR: Unexpected error importing module '{module_name}': {e}")
        return False

def run_import_tests():
    """Runs all import tests and returns True if all pass, False otherwise."""
    all_imports_successful = True

    print("\nTesting core imports...")
    all_imports_successful &= test_import('dad_player')
    all_imports_successful &= test_import('dad_player.core')
    all_imports_successful &= test_import('dad_player.core.image_utils', 'resize_image_data')
    all_imports_successful &= test_import('dad_player.core.settings_manager', 'SettingsManager')
    all_imports_successful &= test_import('dad_player.core.player_engine', 'PlayerEngine')

    print("\nTesting UI imports...")
    all_imports_successful &= test_import('dad_player.ui.screens.main_screen', 'MainScreen')
    all_imports_successful &= test_import('dad_player.ui.widgets.icon_button', 'IconButton')
    all_imports_successful &= test_import('dad_player.ui.screens.library_view', 'LibraryView')
    all_imports_successful &= test_import('dad_player.ui.widgets.album_grid_item', 'AlbumGridItem')
    all_imports_successful &= test_import('dad_player.ui.screens.playlist_view', 'PlaylistView')
    all_imports_successful &= test_import('dad_player.ui.widgets.song_list_item', 'SongListItem')

    print("\nTesting App import...")
    all_imports_successful &= test_import('dad_player.app', 'DadPlayerApp')

    print("\nTesting Config import...")
    all_imports_successful &= test_import('dad_player.config_manager', 'ConfigManager')

    print("\nTesting Utils import...")
    all_imports_successful &= test_import('dad_player.utils')

    print("\nAll test imports completed.")
    return all_imports_successful

class ImportResultApp(App):
    """Displays the import test results in a popup."""
    def __init__(self, import_success, **kwargs):
        super().__init__(**kwargs)
        self.import_success = import_success
        self.popup = None

    def build(self):
        if self.import_success:
            text = "All import tests completed successfully!"
        else:
            text = "One or more import tests failed. See console for details."

        box = BoxLayout(orientation='vertical')
        label = Label(text=text)
        box.add_widget(label)

        self.popup = Popup(
            title='Import Test Results',
            content=box,
            size_hint=(None, None),
            size=(400, 200),
            auto_dismiss=False
        )
        self.popup.open()

        Clock.schedule_once(self.close_app, 3)  # Close after 3 seconds

        return Label(text="Running DadPlayerApp...")  # Dummy label

    def close_app(self, dt):
        """Closes the popup and quits the app."""
        if self.popup:
            self.popup.dismiss()
        App.get_running_app().stop()

def main():
    """Main entry point of the application."""
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    icons_dir = os.path.join(assets_dir, "icons")
    if not os.path.exists(icons_dir):
        try:
            os.makedirs(icons_dir)
        except OSError as e:
            print(f"Could not create icons directory {icons_dir}: {e}", file=sys.stderr)

    # Run import tests *before* initializing DadPlayerApp
    import_success = run_import_tests()

    # Display import test results
    message_app = ImportResultApp(import_success)
    message_app.run()

    if import_success:
        try:
            from dad_player.app import DadPlayerApp
            DadPlayerApp().run()
        except ImportError as e:
            print(f"FATAL ERROR: Could not import DadPlayerApp: {e}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Import tests failed. DadPlayerApp will not be started.")
        sys.exit(1)

if __name__ == "__main__":
    main()