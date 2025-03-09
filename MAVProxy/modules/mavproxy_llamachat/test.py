from MAVProxy.modules.lib import mp_module
from MAVProxy.modules.lib import mp_util
import wx
import requests
import threading

API_BASE_URL = "https://llama8b.gaia.domains/v1"
MODEL_NAME = "llama"
API_KEY = "GAIA"

class LlamaChatFrame(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Llama Chat", size=(600, 400))
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.chat_history = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.input_field = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        send_button = wx.Button(panel, label="Send")
        
        vbox.Add(self.chat_history, 1, wx.EXPAND | wx.ALL, 5)
        vbox.Add(self.input_field, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(send_button, 0, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(vbox)
        
        self.input_field.Bind(wx.EVT_TEXT_ENTER, self.on_send)
        send_button.Bind(wx.EVT_BUTTON, self.on_send)
        
    def on_send(self, event):
        message = self.input_field.GetValue()
        if message:
            self.chat_history.AppendText(f"You: {message}\n")
            self.input_field.SetValue("")
            threading.Thread(target=self.send_to_llama, args=(message,)).start()
            
    def send_to_llama(self, message):
        try:
            response = requests.post(
                f"{API_BASE_URL}/completions",
                headers={"Authorization": f"Bearer {API_KEY}"},
                json={
                    "model": MODEL_NAME,
                    "prompt": message,
                    "max_tokens": 150
                }
            )
            if response.status_code == 200:
                reply = response.json()["choices"][0]["text"]
                wx.CallAfter(self.chat_history.AppendText, f"Assistant: {reply}\n")
            else:
                wx.CallAfter(self.chat_history.AppendText, "Error: Failed to get response\n")
        except Exception as e:
            wx.CallAfter(self.chat_history.AppendText, f"Error: {str(e)}\n")

class LlamaChatModule(mp_module.MPModule):
    def __init__(self, mpstate):
        super(LlamaChatModule, self).__init__(mpstate, "llamachat", "Llama chat window")
        self.add_command('llamachat', self.cmd_llamachat, "Open Llama chat window")
        self.chat_window = None
        
    def cmd_llamachat(self, args):
        if not mp_util.has_wxpython:
            print("llamachat: wxPython not installed")
            return
        if self.chat_window is None:
            self.chat_window = LlamaChatFrame()
        self.chat_window.Show()

def init(mpstate):
    '''Initialize module'''
    return LlamaChatModule(mpstate)