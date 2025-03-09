#!/usr/bin/env python3
'''
Custom Chat Module for MAVProxy
Allows chatting with Google's Gemini AI model

AP_FLAKE8_CLEAN
'''

from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
import sys
import os
import subprocess
import tempfile
import json

class CustomChatModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(CustomChatModule, self).__init__(mpstate, "custom_chat", "Gemini Chat Interface")
        self.add_command('custom_chat', self.cmd_custom_chat, "Open Gemini chat window")
        self.window_process = None
        self.temp_dir = None
        self.api_key = None
        self.config_file = os.path.join(os.path.expanduser("~"), ".mavproxy_custom_chat.json")
        
        # Load API key if it exists
        self.load_api_key()
        
    def load_api_key(self):
        '''Load API key from config file'''
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.api_key = config.get('api_key', None)
                    print("custom_chat: API key loaded from config file")
            except Exception as e:
                print(f"custom_chat: Failed to load API key: {e}")
                
    def save_api_key(self, api_key):
        '''Save API key to config file'''
        try:
            config = {'api_key': api_key}
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            self.api_key = api_key
            print("custom_chat: API key saved to config file")
        except Exception as e:
            print(f"custom_chat: Failed to save API key: {e}")
        
    def launch_chat_window(self):
        '''Launch chat window as a separate process'''
        try:
            # Create a temporary directory for our script
            self.temp_dir = tempfile.mkdtemp(prefix="mavproxy_custom_chat_")
            chat_script = os.path.join(self.temp_dir, "custom_chat_window.py")
            print(f"custom_chat: Created temporary script at {chat_script}")
            
            with open(chat_script, 'w') as f:
                f.write('''#!/usr/bin/env python3
import sys
import os

# Ensure environment variables are set properly
os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':0')

print("Starting minimal chat window test...")

try:
    import wx
    print("wxPython imported successfully")
except ImportError as e:
    print(f"ERROR: wxPython not available: {e}")
    sys.exit(1)

# Create a minimal wxPython app
app = wx.App(False)
frame = wx.Frame(None, title="Gemini Chat Test", size=(400, 200))
panel = wx.Panel(frame)

# Make window more noticeable
frame.SetBackgroundColour(wx.Colour(220, 220, 255))
text = wx.StaticText(panel, label="If you can see this, wxPython is working!", pos=(50, 30))
button = wx.Button(panel, label="Close", pos=(150, 100))
button.Bind(wx.EVT_BUTTON, lambda evt: frame.Close())

frame.Center()
frame.Show()
print("Window should be visible now")

# This keeps the window open
app.MainLoop()
''')
            os.chmod(chat_script, 0o755)

            # Different approach: Launch in terminal window if available
            try:
                # Try with xterm first
                self.window_process = subprocess.Popen(['xterm', '-e', f'python3 {chat_script}; read -p "Press Enter to continue..."'])
                print("custom_chat: Launched with xterm")
            except FileNotFoundError:
                try:
                    # Try with gnome-terminal
                    self.window_process = subprocess.Popen(['gnome-terminal', '--', 'python3', chat_script])
                    print("custom_chat: Launched with gnome-terminal")
                except FileNotFoundError:
                    # Fall back to direct Python execution
                    print("custom_chat: Launching directly with Python")
                    env = os.environ.copy()
                    self.window_process = subprocess.Popen(
                        [sys.executable, chat_script],
                        env=env,
                        start_new_session=True  # This is key - creates a new process group
                    )
                    
            print(f"custom_chat: Process started with PID: {self.window_process.pid}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"custom_chat: Failed to launch window: {e}")
    
    def cmd_custom_chat(self, args):
        '''Command handler for custom_chat'''
        if len(args) > 0 and args[0] == 'set_key':
            if len(args) > 1:
                self.save_api_key(args[1])
                print("custom_chat: API key set successfully")
            else:
                print("custom_chat: Please provide an API key, e.g., 'custom_chat set_key YOUR_API_KEY'")
            return
            
        if self.window_process is None or self.window_process.poll() is not None:
            self.launch_chat_window()
        else:
            print("custom_chat: Chat window is already running")
    
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
    return CustomChatModule(mpstate)