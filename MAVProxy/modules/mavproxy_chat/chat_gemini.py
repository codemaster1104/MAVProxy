'''
AI Chat Module Gemini interface
MAVProxy chat Gemini API with tool calling support

AP_FLAKE8_CLEAN
'''

from pymavlink import mavutil
import time
import re
from datetime import datetime
from threading import Thread, Lock
import json
import math
from MAVProxy.modules.lib import param_help
import os

try:
    import google.generativeai as genai
except ImportError:
    print("chat: failed to import google.generativeai. Install with: pip install google-generativeai")


class ChatGemini:
    def __init__(self, mpstate, status_cb=None, reply_cb=None, wait_for_command_ack_fn=None):
        # keep reference to mpstate
        self.mpstate = mpstate

        # keep reference to status callback
        self.status_cb = status_cb
        self.reply_cb = reply_cb

        # keep reference to wait_for_command_ack_fn
        self.wait_for_command_ack_fn = wait_for_command_ack_fn

        # lock to prevent multiple threads sending text to the assistant at the same time
        self.send_lock = Lock()

        # wakeup timer array
        self.wakeup_schedule = []
        self.thread = Thread(target=self.check_wakeup_timers)
        self.thread.daemon = True
        self.thread.start()

        # initialise Gemini connection
        self.api_key = None
        self.config_file = os.path.join(os.path.expanduser("~"), ".gemini_api_key")
        self.load_api_key()
        
        # Model and chat session
        self.model = None
        self.chat = None
        
        # Initialize with available tools
        self.tools = self.define_tools()

    def load_api_key(self):
        """Load API key from config file"""
        import os
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.api_key = f.read().strip()
                print("chat: Loaded Gemini API key from config file")
                self.initialize_model()
            except Exception as e:
                print(f"chat: Failed to load API key: {e}")

    def save_api_key(self, api_key):
        """Save API key to config file"""
        import os
        try:
            with open(self.config_file, 'w') as f:
                f.write(api_key)
            self.api_key = api_key
            print("chat: Saved Gemini API key to config file")
            return self.initialize_model()
        except Exception as e:
            print(f"chat: Failed to save API key: {e}")
            return False

    def initialize_model(self):
        """Initialize the Gemini model with current API key"""
        try:
            genai.configure(api_key=self.api_key)
            
            # Define tool configurations
            tool_configs = []
            for tool_name, tool_info in self.tools.items():
                tool_configs.append({
                    "function_declarations": [{
                        "name": tool_name,
                        "description": tool_info["description"],
                        "parameters": tool_info["parameters"]
                    }]
                })
            
            # Create model with tools
            self.model = genai.GenerativeModel(
                "gemini-1.5-pro",
                tools=tool_configs
            )
            self.chat = self.model.start_chat(history=[])
            print("chat: Successfully configured Gemini API")
            return True
        except Exception as e:
            print(f"chat: Failed to initialize Gemini model: {e}")
            return False

    def define_tools(self):
        """Define the tools (functions) available to the Gemini model"""
        tools = {
            "get_current_datetime": {
                "description": "Get the current date and time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "_dummy": {  # Add dummy property for functions with no params
                            "type": "string",
                            "description": "This parameter is not used"
                        }
                    },
                    "required": []
                },
                "function": self.get_current_datetime
            },
            "get_vehicle_type": {
                "description": "Get the type of vehicle (Copter, Plane, Rover, etc.)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "_dummy": {
                            "type": "string",
                            "description": "This parameter is not used"
                        }
                    },
                    "required": []
                },
                "function": self.get_vehicle_type
            },
            "get_vehicle_state": {
                "description": "Get the current state of the vehicle including armed status and mode",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "_dummy": {
                            "type": "string",
                            "description": "This parameter is not used"
                        }
                    },
                    "required": []
                },
                "function": self.get_vehicle_state
            },
            # The other functions that already have properties are fine
            "get_parameter": {
                "description": "Get a vehicle parameter value",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the parameter to get"
                        }
                    },
                    "required": ["name"]
                },
                "function": self.get_parameter
            },
            "set_parameter": {
                "description": "Set a vehicle parameter value",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the parameter to set"
                        },
                        "value": {
                            "type": "number",
                            "description": "The value to set the parameter to"
                        }
                    },
                    "required": ["name", "value"]
                },
                "function": self.set_parameter
            },
            "set_vehicle_mode": {
                "description": "Set the vehicle flight mode",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "description": "The mode to set (e.g., 'GUIDED', 'AUTO', 'STABILIZE', etc.)"
                        }
                    },
                    "required": ["mode"]
                },
                "function": self.set_vehicle_mode
            }
        }
        return tools

    def check_connection(self):
        """Check if we can connect to Gemini API"""
        if not self.api_key:
            print("chat: Gemini API key not set. Use 'chat set_gemini_key YOUR_API_KEY'")
            return False
            
        if not self.model:
            if not self.initialize_model():
                return False
                
        try:
            # Test API connection with a simple query
            response = self.model.generate_content("Test connection")
            return True
        except Exception as e:
            print(f"chat: failed to connect to Gemini API: {e}")
            return False

    def send_to_assistant(self, text):
        """Send text to Gemini and process the response with tool calls"""
        with self.send_lock:
            if not self.check_connection():
                self.send_reply("chat: failed to connect to Gemini API")
                return

            try:
                self.send_status("Generating response...")
                
                # Send message to Gemini
                response = self.chat.send_message(text)
                
                # Handle the response including any potential tool calls
                self.handle_gemini_response(response)
                
            except Exception as e:
                error_message = f"Error: {str(e)}"
                print(f"chat: {error_message}")
                self.send_status(error_message)

    def handle_gemini_response(self, response):
        """Process Gemini response and handle any tool calls"""
        if not response or not response.candidates:
            self.send_reply("No response received from Gemini")
            return
            
        # Extract the response parts
        for candidate in response.candidates:
            if not hasattr(candidate, 'content') or not candidate.content:
                continue
                
            # Check for text content
            for part in candidate.content.parts:
                # Handle regular text
                if hasattr(part, 'text') and part.text:
                    self.send_reply(part.text)
                    
                # Handle function calls (tool calls)
                if hasattr(part, 'function_call'):
                    self.handle_function_call(part.function_call)
        
        self.send_status("Ready")

    def handle_function_call(self, function_call):
        """Handle function call from Gemini"""
        # Extract function name and arguments
        func_name = function_call.name
        if not func_name:
            print("chat: Empty function name received")
            return
            
        try:
            arguments = json.loads(function_call.args)
        except:
            arguments = {}
            
        print(f"chat: Handling function call: {func_name}")
        
        # Define supported functions
        supported_funcs = [
            "get_current_datetime",
            "get_vehicle_type",
            "get_vehicle_state",
            "get_parameter",
            "set_parameter"
        ]
        
        # Call function if supported
        output = "Invalid function call"
        func = getattr(self, func_name, None)
        
        if func_name in supported_funcs and func is not None:
            try:
                # Call the function
                output = func(arguments)
            except Exception as e:
                error_message = f"{func_name}: function call failed - {str(e)}"
                print(f"chat: {error_message}")
                output = error_message
        else:
            print(f"chat: Unrecognized function name: {func_name}")
            output = f"Unrecognized function call: {func_name}"
        
        # Send function result back to Gemini
        try:
            result_json = json.dumps(output)
            # For Gemini 1.5, the API is different:
            response = self.chat.send_message(
                f"Function result for {func_name}: {result_json}"
            )
            
            # Process the response to this function call
            self.handle_gemini_response(response)
        except Exception as e:
            print(f"chat: Error sending function response: {e}")

    # Function implementations - reused from the OpenAI implementation
    def get_current_datetime(self, arguments):
        return datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")

    def get_vehicle_type(self, arguments):
        # get vehicle type from latest HEARTBEAT message
        hearbeat_msg = self.mpstate.master().messages.get('HEARTBEAT', None)
        vehicle_type_str = "unknown"
        if hearbeat_msg is not None:
            if hearbeat_msg.type in [mavutil.mavlink.MAV_TYPE_FIXED_WING,
                                    mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR,
                                    mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR,
                                    mavutil.mavlink.MAV_TYPE_VTOL_TILTROTOR]:
                vehicle_type_str = "Plane"
            if hearbeat_msg.type == mavutil.mavlink.MAV_TYPE_GROUND_ROVER:
                vehicle_type_str = "Rover"
            if hearbeat_msg.type == mavutil.mavlink.MAV_TYPE_SURFACE_BOAT:
                vehicle_type_str = "Boat"
            if hearbeat_msg.type == mavutil.mavlink.MAV_TYPE_SUBMARINE:
                vehicle_type_str = "Sub"
            if hearbeat_msg.type in [mavutil.mavlink.MAV_TYPE_QUADROTOR,
                                    mavutil.mavlink.MAV_TYPE_COAXIAL,
                                    mavutil.mavlink.MAV_TYPE_HEXAROTOR,
                                    mavutil.mavlink.MAV_TYPE_OCTOROTOR,
                                    mavutil.mavlink.MAV_TYPE_TRICOPTER,
                                    mavutil.mavlink.MAV_TYPE_DODECAROTOR]:
                vehicle_type_str = "Copter"
            if hearbeat_msg.type == mavutil.mavlink.MAV_TYPE_HELICOPTER:
                vehicle_type_str = "Heli"
            if hearbeat_msg.type == mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER:
                vehicle_type_str = "Tracker"
            if hearbeat_msg.type == mavutil.mavlink.MAV_TYPE_AIRSHIP:
                vehicle_type_str = "Blimp"
        return {
            "vehicle_type": vehicle_type_str
        }
    
    def set_vehicle_mode(self, arguments):
        mode = arguments.get("mode", None)
        if mode is None:
            return "set_vehicle_mode: mode not specified"
        
        # Convert to uppercase for consistency
        mode = mode.upper()
        
        # Attempt to set mode
        try:
            self.mpstate.functions.process_stdin(f"mode {mode}")
            return f"set_vehicle_mode: Requested mode change to {mode}"
        except Exception as e:
            return f"set_vehicle_mode: Failed to set mode to {mode} - {str(e)}"

    def get_vehicle_state(self, arguments):
        # get mode from latest HEARTBEAT message
        hearbeat_msg = self.mpstate.master().messages.get('HEARTBEAT', None)
        if hearbeat_msg is None:
            mode_number = 0
            print("chat: get_vehicle_state: vehicle mode is unknown")
        else:
            mode_number = hearbeat_msg.custom_mode
        return {
            "armed": (self.mpstate.master().motors_armed() > 0),
            "mode": mode_number
        }

    def get_parameter(self, arguments):
        param_name = arguments.get("name", None)
        if param_name is None:
            return "get_parameter: name not specified"

        # start with empty parameter list
        param_list = {}

        # handle param name containing regex
        if self.contains_regex(param_name):
            pattern = re.compile(param_name)
            for existing_param_name in sorted(self.mpstate.mav_param.keys()):
                if pattern.match(existing_param_name) is not None:
                    param_value = self.mpstate.functions.get_mav_param(existing_param_name, None)
                    if param_value is None:
                        print("chat: get_parameter unable to get " + existing_param_name)
                    else:
                        param_list[existing_param_name] = param_value
        else:
            # handle simple case of a single parameter name
            param_value = self.mpstate.functions.get_mav_param(param_name, None)
            if param_value is None:
                return "get_parameter: " + param_name + " parameter not found"
            param_list[param_name] = param_value

        return param_list

    def set_parameter(self, arguments):
        param_name = arguments.get("name", None)
        if param_name is None:
            return "set_parameter: parameter name not specified"
        param_value = arguments.get("value", None)
        if param_value is None:
            return "set_parameter: value not specified"
        self.mpstate.functions.param_set(param_name, param_value, retries=3)
        return "set_parameter: parameter value set"

    # Support functions
    def check_wakeup_timers(self):
        while True:
            # wait for one second
            time.sleep(1)

            # check if any timers are set
            if len(self.wakeup_schedule) == 0:
                continue

            # get current time
            now = time.time()

            # check if any timers have expired
            for wakeup_timer in list(self.wakeup_schedule):
                if now >= wakeup_timer["time"]:
                    # send message to assistant
                    message = "WAKEUP:" + wakeup_timer["message"]
                    self.send_to_assistant(message)

                    # remove from wakeup schedule
                    self.wakeup_schedule.remove(wakeup_timer)

    def send_status(self, status):
        if self.status_cb:
            self.status_cb(status)

    def send_reply(self, reply):
        if self.reply_cb:
            self.reply_cb(reply)

    def contains_regex(self, string):
        regex_characters = ".^$*+?{}[]\\|()"
        for x in regex_characters:
            if string.count(x):
                return True
        return False
    










# '''
# AI Chat Module Gemini interface

# Google Generative AI (Gemini) API integration for MAVProxy chat

# AP_FLAKE8_CLEAN
# '''

# import time
# import json
# import os.path
# from threading import Lock

# try:
#     import google.generativeai as genai
# except ImportError:
#     print("chat: failed to import google.generativeai. Install with: pip install google-generativeai")

# class ChatGemini:
#     def __init__(self, mpstate, status_cb=None, reply_cb=None):
#         # API configuration
#         self.api_key = None
#         self.config_file = os.path.join(os.path.expanduser("~"), ".gemini_api_key")
#         self.load_api_key()
        
#         # Keep references to callbacks and state
#         self.mpstate = mpstate
#         self.status_cb = status_cb
#         self.reply_cb = reply_cb
#         self.send_lock = Lock()
        
#         # Initialize model only if API key is available
#         self.model = None
#         self.chat = None
#         if self.api_key:
#             self.initialize_model()
    
#     def load_api_key(self):
#         """Load API key from config file"""
#         if os.path.exists(self.config_file):
#             try:
#                 with open(self.config_file, 'r') as f:
#                     self.api_key = f.read().strip()
#                 print("chat: Loaded Gemini API key from config file")
#             except Exception as e:
#                 print(f"chat: Failed to load API key: {e}")
    
#     def save_api_key(self, api_key):
#         """Save API key to config file"""
#         try:
#             with open(self.config_file, 'w') as f:
#                 f.write(api_key)
#             self.api_key = api_key
#             print("chat: Saved Gemini API key to config file")
            
#             # Initialize model with new API key
#             return self.initialize_model()
#         except Exception as e:
#             print(f"chat: Failed to save API key: {e}")
#             return False
    
#     def initialize_model(self):
#         """Initialize the Gemini model with current API key"""
#         try:
#             genai.configure(api_key=self.api_key)
            
#             # Use the recommended newer model directly
#             model_name = "gemini-1.5-flash"
#             print(f"chat: Using model {model_name}")
#             self.model = genai.GenerativeModel(model_name)
#             self.chat = self.model.start_chat(history=[])
#             print("chat: Successfully configured Gemini API")
#             return True
#         except Exception as e:
#             print(f"chat: Failed to initialize Gemini model: {e}")
#             return False

#     def check_connection(self):
#         if not self.api_key:
#             print("chat: Gemini API key not set. Use 'chat set_gemini_key YOUR_API_KEY'")
#             return False
            
#         if not self.model:
#             if not self.initialize_model():
#                 return False
                
#         try:
#             # Test API connection with a simple query
#             response = self.model.generate_content("Test connection")
#             return True
#         except Exception as e:
#             print(f"chat: failed to connect to Gemini API: {e}")
#             return False

#     def send_to_assistant(self, text):
#         with self.send_lock:
#             if not self.check_connection():
#                 self.send_reply("chat: failed to connect to Gemini API")
#                 return

#             try:
#                 self.send_status("Generating response...")
#                 response = self.chat.send_message(text)
#                 if response:
#                     self.send_reply(response.text)
#                     self.send_status("Ready")
#                 else:
#                     self.send_status("Error: No response from Gemini")
#             except Exception as e:
#                 error_message = f"Error: {str(e)}"
#                 print(f"chat: {error_message}")
#                 self.send_status(error_message)

#     def send_status(self, status):
#         if self.status_cb:
#             self.status_cb(status)

#     def send_reply(self, reply):
#         if self.reply_cb:
#             self.reply_cb(reply)
