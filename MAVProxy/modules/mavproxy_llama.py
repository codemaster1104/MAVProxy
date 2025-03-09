from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
import wx
import threading
import requests

API_BASE_URL = "https://llama8b.gaia.domains/v1"
MODEL_NAME = "llama"
API_KEY = "GAIA"

class LlamaChatWindow(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Llama Chat", size=(600, 400))
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.chat_history = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY)
        self.input_field = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.send_button = wx.Button(panel, label="Send")
        
        vbox.Add(self.chat_history, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.input_field, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.send_button, 0, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(vbox)
        
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.input_field.Bind(wx.EVT_TEXT_ENTER, self.on_send)
        self.send_button.Bind(wx.EVT_BUTTON, self.on_send)
        
        self.set_status("Ready")
    
    def on_close(self, event):
        # hide the window instead of destroying it
        self.Hide()
    
    def on_send(self, event):
        message = self.input_field.GetValue()
        if message:
            self.append_text(f"You: {message}\n")
            self.input_field.SetValue("")
            self.set_status("Sending...")
            threading.Thread(target=self.send_to_llama, args=(message,), daemon=True).start()
    
    def send_to_llama(self, message):
        try:
            response = requests.post(
                f"{API_BASE_URL}/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={"model": MODEL_NAME, "prompt": message, "max_tokens": 150}
            )
            if response.status_code == 200:
                reply = response.json()["choices"][0]["text"]
                wx.CallAfter(self.append_text, f"Assistant: {reply}\n")
                wx.CallAfter(self.set_status, "Ready")
            else:
                wx.CallAfter(self.set_status, f"Error: {response.status_code}")
        except Exception as e:
            wx.CallAfter(self.set_status, f"Error: {str(e)}")
    
    def append_text(self, text):
        self.chat_history.AppendText(text)
    
    def set_status(self, text):
        self.status_text.SetValue(text)

class LlamaChatModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(LlamaChatModule, self).__init__(mpstate, "llama", "Llama chat interface")
        print("llama: Module initializing...")
        self.add_command('llama', self.cmd_llama, "Show Llama chat window")
        self.chat_window = None
        self.app = None
        
        # Initialize GUI immediately
        print("llama: Starting GUI initialization...")
        self.init_gui()
        print("llama: GUI initialization completed")
        
    def init_gui(self):
        if not mp_util.has_wxpython:
            print("llama: wxPython not installed")
            return
            
        try:
            print("llama: Checking for existing wx.App")
            app = wx.GetApp()
            if app is None:
                print("llama: Creating new wx.App")
                self.app = wx.App(False)
            else:
                print("llama: Using existing wx.App")
                self.app = app
            
            print("llama: Creating window")
            self.chat_window = LlamaChatWindow()
            self.chat_window.Show()
            print("llama: Window created and shown")
            
        except Exception as e:
            print(f"llama: GUI initialization failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def cmd_llama(self, args):
        print("llama: Command received")
        if not self.chat_window:
            print("llama: Window not initialized yet")
            return
            
        print("llama: Showing window")
        self.chat_window.Show()
        self.chat_window.Raise()
        print("llama: Window shown and raised")

def init(mpstate):
    print("llama: Module init called")
    return LlamaChatModule(mpstate)