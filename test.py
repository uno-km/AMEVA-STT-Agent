import sys
import traceback
try:
    import gui.panels.settings_panel
    with open("err.log", "w") as f:
        f.write("Success\n")
except Exception as e:
    with open("err.log", "w") as f:
        traceback.print_exc(file=f)
