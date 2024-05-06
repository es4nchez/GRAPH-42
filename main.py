import tkinter as tk
from tkinter import messagebox, scrolledtext, Listbox
from pygments import lex
from pygments.lexers import JsonLexer
from pygments.styles import get_style_by_name
from pygments.style import Style
from pygments.token import Token
import requests
import json
import yaml

class SolarizedDarkStyle(Style):
    default_style = ""
    styles = {
        Token.String: '#2aa198',  # teal
        Token.Number: '#d33682',  # magenta
        Token.Keyword: '#859900',  # green
        Token.Literal: '#dc322f',  # red
        Token.Operator: '#6c71c4',  # violet
        Token.Punctuation: '#93a1a1',  # base1
        Token.Text: '#839496',  # base00
        Token.Other: '#cb4b16',  # orange
    }

class IntraAPIClient(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)

        with open('config.yml', 'r') as cfg_stream:
            config = yaml.load(cfg_stream, Loader=yaml.BaseLoader)
            self.client_id = config['intra']['client']
            self.client_secret = config['intra']['secret']


        self.master = master
        self.pack(fill=tk.BOTH, expand=True)
        self.create_widgets()
        self.token = None
        self.payload_entries = []

        self.json_keys_listbox = Listbox(self.response_frame)
        self.json_keys_listbox.pack(side=tk.LEFT, fill=tk.Y)
        self.json_keys_listbox.bind('<<ListboxSelect>>', self.on_key_select)

        self.response_text = scrolledtext.ScrolledText(self.response_frame)
        self.response_text.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def on_key_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            key = event.widget.get(index)
            self.display_values_for_key(key)

    def display_values_for_key(self, key):
        values = [str(item[key]) for item in self.current_json_data if key in item]
        self.response_text.delete('1.0', tk.END)
        self.response_text.insert(tk.END, '\n'.join(values))

    def create_widgets(self):
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Left panel
        self.request_frame = tk.Frame(self.paned_window, width=500)
        self.paned_window.add(self.request_frame)

        self.client_id_label = tk.Label(self.request_frame, text="Client ID:")
        self.client_id_label.pack()
        self.client_id_entry = tk.Entry(self.request_frame)
        self.client_id_entry.insert(0, self.client_id)
        self.client_id_entry.pack()

        self.client_secret_label = tk.Label(self.request_frame, text="Client Secret:")
        self.client_secret_label.pack()
        self.client_secret_entry = tk.Entry(self.request_frame)
        self.client_secret_entry.insert(0, self.client_secret)
        self.client_secret_entry.pack()

        self.authenticate_button = tk.Button(self.request_frame, text="Authenticate", command=self.authenticate)
        self.authenticate_button.pack()

        self.endpoint_label = tk.Label(self.request_frame, text="API Endpoint:")
        self.endpoint_label.pack()
        self.endpoint_entry = tk.Entry(self.request_frame)
        self.endpoint_entry.pack()

        self.add_payload_button = tk.Button(self.request_frame, text="Add Payload", command=self.add_payload_field)
        self.add_payload_button.pack()

        self.request_button = tk.Button(self.request_frame, text="Send Request", command=self.send_request)
        self.request_button.pack()

        # Right panel
        self.response_frame = tk.Frame(self.paned_window, width=200)
        self.paned_window.add(self.response_frame)

        self.response_text = scrolledtext.ScrolledText(self.response_frame)
        self.response_text.pack(fill=tk.BOTH, expand=True)

    def add_payload_field(self):
        frame = tk.Frame(self.request_frame)
        frame.pack()

        key_entry = tk.Entry(frame, width=10)
        key_entry.pack(side=tk.LEFT)
        key_entry.insert(0, "Key")
        value_entry = tk.Entry(frame, width=10)
        value_entry.pack(side=tk.LEFT)
        value_entry.insert(0, "Value")

        self.payload_entries.append((key_entry, value_entry))

    def authenticate(self):
        url = 'https://api.intra.42.fr/oauth/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id_entry.get(),
            'client_secret': self.client_secret_entry.get()
        }
        response = requests.post(url, data=data)
        if response.status_code == 200:
            self.token = response.json()['access_token']
            messagebox.showinfo("Authentication", "Authentication Successful!")
        else:
            messagebox.showerror("Authentication", "Failed to authenticate")

    def send_request(self):
        if not self.token:
            messagebox.showerror("Error", "Authenticate first!")
            return

        endpoint = self.endpoint_entry.get()
        url = f'https://api.intra.42.fr/v2/{endpoint}'
        headers = {'Authorization': f'Bearer {self.token}'}
        payload = {entry[0].get(): entry[1].get() for entry in self.payload_entries}
        print(payload)
        print("Sending request with payload:", payload)

        response = requests.get(url, headers=headers, params=payload)
        print(response)
        if response.status_code == 200:
           # print(response.headers)
            self.response_text.delete('1.0', tk.END)
            self.current_json_data = response.json()
            self.update_json_keys_listbox(self.current_json_data)
        else:
            messagebox.showerror("Request Failed", f"HTTP Status Code: {response.status_code}")

    def update_json_keys_listbox(self, json_data):
        self.json_keys_listbox.delete(0, tk.END)
        if isinstance(json_data, list) and json_data:
            keys = json_data[0].keys()
            for key in keys:
                self.json_keys_listbox.insert(tk.END, key)

    def apply_syntax_highlighting(self, json_data):
        style = SolarizedDarkStyle()
        lexer = JsonLexer()
        tokens = lex(json_data, lexer)
        for ttype, value in tokens:
            tag_name = str(ttype)
            self.response_text.tag_configure(tag_name, foreground=style.styles[ttype])
            self.response_text.insert(tk.END, value, tag_name)

root = tk.Tk()
root.title("Gr4fik")
root.geometry("1200x700")
app = IntraAPIClient(master=root)
app.mainloop()
