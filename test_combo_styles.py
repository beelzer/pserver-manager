from qtframework import Application
from qtframework.utils import ResourceManager
import sys

rm = ResourceManager()
app = Application(sys.argv, resource_manager=rm)
app.theme_manager.set_theme('dark')
sheet = app.theme_manager.get_stylesheet()

# Find QComboBox styles
lines = sheet.split('\n')
in_combo = False
for line in lines:
    if 'QComboBox' in line:
        in_combo = True
    if in_combo:
        print(line)
        if line.strip().startswith('/*') and 'QComboBox' not in line:
            break
