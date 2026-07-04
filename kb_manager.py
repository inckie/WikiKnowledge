#!/usr/bin/env python
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
import json
import subprocess
import threading
import os
import sys

CONFIG_FILE = "config.json"

class KBManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Knowledge Base Manager")
        self.root.geometry("800x600")
        
        self.kbs = {}
        self.processes = {}
        
        self.load_config()
        self.build_ui()
        
        # Ensure cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                self.kbs = json.load(f).get("knowledge_bases", {})
        except Exception as e:
            print(f"Failed to load config: {e}")
            
    def build_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.tabs = {}
        for kb_id, kb_info in self.kbs.items():
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=kb_id)
            
            # Control frame
            ctrl_frame = ttk.Frame(frame)
            ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
            
            toggle_btn = ttk.Button(ctrl_frame, text="Start", command=lambda k_id=kb_id: self.toggle_kb(k_id))
            toggle_btn.pack(side=tk.LEFT, padx=5)
            
            status_lbl = ttk.Label(ctrl_frame, text="Status: Stopped")
            status_lbl.pack(side=tk.LEFT, padx=10)
            
            lbl = ttk.Label(ctrl_frame, text=f"Port: {kb_info['port']} | Path: {kb_info.get('kb_dir', 'N/A')}")
            lbl.pack(side=tk.LEFT)
            
            # Log area
            log_area = scrolledtext.ScrolledText(frame, state='disabled', wrap=tk.WORD)
            log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            self.tabs[kb_id] = {
                'toggle_btn': toggle_btn,
                'status_lbl': status_lbl,
                'log_area': log_area
            }
            self.update_buttons(kb_id, False)

    def append_log(self, kb_id, text):
        log_area = self.tabs[kb_id]['log_area']
        log_area.config(state='normal')
        log_area.insert(tk.END, text)
        log_area.see(tk.END)
        log_area.config(state='disabled')
        
    def read_stream(self, process, kb_id, stream_name):
        stream = getattr(process, stream_name)
        while True:
            line = stream.readline()
            if not line:
                break
            # Use root.after to safely update the GUI from a thread
            self.root.after(0, self.append_log, kb_id, line.decode('utf-8', errors='replace'))

    def toggle_kb(self, kb_id):
        if kb_id in self.processes and self.processes[kb_id].poll() is None:
            self.stop_kb(kb_id)
        else:
            self.start_kb(kb_id)

    def start_kb(self, kb_id):
        if kb_id in self.processes and self.processes[kb_id].poll() is None:
            return # Already running
            
        kb_info = self.kbs[kb_id]
        cmd = ["uv", "run", "python", "run.py", f"--port={kb_info['port']}"]
        if kb_info.get("kb_dir"):
            cmd.append(f"--kb-dir={kb_info['kb_dir']}")
            
        try:
            # CREATE_NEW_PROCESS_GROUP flag helps prevent Ctrl+C in terminal from killing this process if we run it from a terminal
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(__file__)),
                creationflags=creationflags
            )
            self.processes[kb_id] = process
            
            # Start threads to read stdout and stderr
            threading.Thread(target=self.read_stream, args=(process, kb_id, 'stdout'), daemon=True).start()
            threading.Thread(target=self.read_stream, args=(process, kb_id, 'stderr'), daemon=True).start()
            
            self.update_buttons(kb_id, True)
            self.append_log(kb_id, f"--- Started {kb_id} (PID: {process.pid}) ---\n")
            
        except Exception as e:
            self.append_log(kb_id, f"Failed to start: {e}\n")

    def kill_process_tree(self, pid):
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            # Fallback for non-Windows (though this script is tailored for Windows)
            import signal
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                pass

    def stop_kb(self, kb_id):
        if kb_id in self.processes:
            process = self.processes[kb_id]
            if process.poll() is None:
                self.kill_process_tree(process.pid)
                self.append_log(kb_id, f"--- Stopped {kb_id} ---\n")
            self.update_buttons(kb_id, False)
            
    def update_buttons(self, kb_id, is_running):
        tab = self.tabs[kb_id]
        if is_running:
            tab['toggle_btn'].config(text="Stop")
            tab['status_lbl'].config(text="Status: Running")
        else:
            tab['toggle_btn'].config(text="Start")
            tab['status_lbl'].config(text="Status: Stopped")

    def on_close(self):
        for kb_id, process in self.processes.items():
            if process.poll() is None:
                self.kill_process_tree(process.pid)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = KBManagerApp(root)
    root.mainloop()
