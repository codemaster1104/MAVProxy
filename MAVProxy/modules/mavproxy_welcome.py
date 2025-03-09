#!/usr/bin/env python3
'''
Welcome Module for MAVProxy
Displays a welcome message for ArduPilot

AP_FLAKE8_CLEAN
'''

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
import sys
import os
import subprocess
import tempfile

class WelcomeModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(WelcomeModule, self).__init__(mpstate, "welcome", "ArduPilot Welcome Screen")
        self.add_command('welcome', self.cmd_welcome, "Show welcome screen")
        self.window_process = None
        self.temp_dir = None
        
        # Launch welcome window on module load
        self.launch_welcome_window()
        
    def launch_welcome_window(self):
        '''Launch welcome window as a separate process'''
        try:
            # Create a temporary directory for our script
            self.temp_dir = tempfile.mkdtemp(prefix="mavproxy_welcome_")
            welcome_script = os.path.join(self.temp_dir, "welcome_window.py")
            
            with open(welcome_script, 'w') as f:
                f.write('''#!/usr/bin/env python3
import sys
try:
    import wx
except ImportError:
    print("wxPython not available")
    sys.exit(1)
    
app = wx.App(False)
frame = wx.Frame(None, title="ArduPilot Welcome", size=(600, 400))
panel = wx.Panel(frame)
sizer = wx.BoxSizer(wx.VERTICAL)

# Title
title_font = wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
title = wx.StaticText(panel, label="Welcome to ArduPilot")
title.SetFont(title_font)

# Message
message = wx.StaticText(panel, label="""
ArduPilot is an open source autopilot system supporting:
- Multi-copters
- Traditional helicopters
- Fixed wing aircraft
- Rovers
- Submarines
- Antenna trackers

Use the MAVProxy interface to control and monitor your vehicle.
""")

# Button
close_button = wx.Button(panel, label="Close")
close_button.Bind(wx.EVT_BUTTON, lambda evt: frame.Close())

# Layout
sizer.Add(title, 0, wx.ALIGN_CENTER | wx.ALL, 20)
sizer.Add(message, 0, wx.EXPAND | wx.ALL, 20)
sizer.AddStretchSpacer()
sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 20)

panel.SetSizer(sizer)
frame.Center()
frame.Show()
app.MainLoop()
''')
            os.chmod(welcome_script, 0o755)  # Make it executable
            
            print(f"welcome: Launching welcome window from {welcome_script}")
            
            # Use subprocess to launch in a separate process
            self.window_process = subprocess.Popen([sys.executable, welcome_script])
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"welcome: Failed to launch window: {str(e)}")
    
    def cmd_welcome(self, args):
        '''Command handler for welcome'''
        if self.window_process is None or self.window_process.poll() is not None:
            self.launch_welcome_window()
        else:
            print("welcome: Window is already running")
    
    def unload(self):
        '''unload module'''
        if self.window_process is not None and self.window_process.poll() is None:
            self.window_process.terminate()
            
        # Clean up temporary directory if it exists
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass

def init(mpstate):
    '''initialize module'''
    return WelcomeModule(mpstate)



