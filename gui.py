import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import os
import main
import glob2 as glob
import argparse
import sys
import json

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

class AgentSystemGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Agent System: Hello World")
        self.root.geometry("600x600")  # Increased height for status bar
        
        # Output queues
        self.output_queue = queue.Queue()
        self.console_queue = queue.Queue()  # For console tab
        
        # Flag to control output processing
        self.running = True
        self.execution_thread = None
        
        # Load tasks from tasks.json if it exists
        self.tasks = []
        tasks_path = os.path.join(os.getcwd(), "config", "tasks.json")
        if os.path.exists(tasks_path):
            try:
                with open(tasks_path, "r") as f:
                    data = json.load(f)
                    self.tasks = data["tasks"] if "tasks" in data else []
                print("Loaded tasks:", self.tasks)
            except Exception as e:
                print(f"Failed to load tasks.json: {e}")
                self.tasks = []
        
        # Create GUI elements
        self.create_widgets()
        self.create_status_bar()
        self.update_hw_status()  # <-- Add this line
        
        # Start output processing
        self.process_output_queue()
        self.process_console_queue()

    def create_widgets(self):
        # Button frame
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=5, padx=5, fill=tk.X)
        
        # Run button
        self.run_button = ttk.Button(button_frame, text="Run Agent System", command=self.run_system)
        self.run_button.pack(side=tk.LEFT, padx=5)
        
        # View code button
        self.code_button = ttk.Button(button_frame, text="View Source Code", command=self.view_source_code)
        self.code_button.pack(side=tk.LEFT, padx=5)
        
        # View test results button
        self.test_button = ttk.Button(button_frame, text="View Test Results", command=self.view_test_results)
        self.test_button.pack(side=tk.LEFT, padx=5)
        
        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        
        # Log tab
        self.log_text = scrolledtext.ScrolledText(self.notebook, height=20, width=70, wrap=tk.WORD)
        self.log_text.config(state='disabled')
        self.notebook.add(self.log_text, text="Log")
        
        # Console tab
        self.console_text = scrolledtext.ScrolledText(self.notebook, height=20, width=70, wrap=tk.WORD, foreground='white', background='black')
        self.console_text.config(state='disabled')
        self.notebook.add(self.console_text, text="Console")
        
        # Tasks tab
        self.tasks_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.tasks_frame, text="Tasks")
        self.create_tasks_tab()

        # LLM tab
        self.llm_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.llm_frame, text="LLM")
        self.create_llm_tab()

        # Chat tab
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="Chat")
        self.create_chat_tab()

        # Enable copying from log_text and console_text
        self.setup_copy_functionality()
        
        # Debug button clicks
        self.run_button.bind("<Button-1>", lambda e: print("Run button clicked"))
        self.code_button.bind("<Button-1>", lambda e: print("View Source Code button clicked"))
        self.test_button.bind("<Button-1>", lambda e: print("View Test Results button clicked"))

    def create_tasks_tab(self):
        # Listbox for tasks
        self.tasks_listbox = tk.Listbox(self.tasks_frame, height=12)
        self.tasks_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(self.tasks_frame, orient="vertical", command=self.tasks_listbox.yview)
        self.tasks_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        # Button frame
        btn_frame = ttk.Frame(self.tasks_frame)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        add_btn = ttk.Button(btn_frame, text="Add Task", command=self.add_task)
        add_btn.pack(fill=tk.X, pady=2)
        edit_btn = ttk.Button(btn_frame, text="Edit Task", command=self.edit_task)
        edit_btn.pack(fill=tk.X, pady=2)
        del_btn = ttk.Button(btn_frame, text="Delete Task", command=self.delete_task)
        del_btn.pack(fill=tk.X, pady=2)

        self.refresh_tasks_listbox()

    def refresh_tasks_listbox(self):
        self.tasks_listbox.delete(0, tk.END)
        for idx, task in enumerate(self.tasks):
            desc = task["description"] if isinstance(task, dict) and "description" in task else str(task)
            self.tasks_listbox.insert(tk.END, f"{idx+1}. {desc}")

    def add_task(self):
        task_desc = self.simple_input_dialog("Add Task", "Enter new task description:")
        if task_desc:
            # Generate a new ID based on existing tasks
            new_id = max([t.get("id", 0) for t in self.tasks] + [0]) + 1
            new_task = {
                "id": new_id,
                "description": task_desc,
                "type": "code"  # Default; can be edited in JSON later if needed
            }
            self.tasks.append(new_task)
            self.refresh_tasks_listbox()
            self.save_tasks()

    def edit_task(self):
        selection = self.tasks_listbox.curselection()
        if not selection:
            messagebox.showinfo("Edit Task", "Please select a task to edit.")
            return
        idx = selection[0]
        current_task = self.tasks[idx]
        # Get initial value based on type
        initial = current_task["description"] if isinstance(current_task, dict) and "description" in current_task else str(current_task)
        new_desc = self.simple_input_dialog("Edit Task", "Edit task description:", initialvalue=initial)
        if new_desc:
            if isinstance(self.tasks[idx], dict):
                self.tasks[idx]["description"] = new_desc
            else:
                # Convert str to dict for consistency
                self.tasks[idx] = {
                    "id": idx + 1,  # Fallback ID
                    "description": new_desc,
                    "type": "code"
                }
            self.refresh_tasks_listbox()
            self.save_tasks()

    def delete_task(self):
        selection = self.tasks_listbox.curselection()
        if not selection:
            messagebox.showinfo("Delete Task", "Please select a task to delete.")
            return
        idx = selection[0]
        del self.tasks[idx]
        # Optional: Re-number IDs to avoid gaps
        for i, task in enumerate(self.tasks):
            if isinstance(task, dict):
                task["id"] = i + 1
        self.refresh_tasks_listbox()
        self.save_tasks()

    def save_tasks(self):
        data = {"tasks": self.tasks}
        try:
            with open(self.tasks_path, "w") as f:
                json.dump(data, f, indent=4)  # indent for readability
            print("Saved tasks to", self.tasks_path)
        except Exception as e:
            print(f"Failed to save {self.tasks_path}: {e}")
            messagebox.showerror("Save Error", f"Could not save tasks: {e}")

    def simple_input_dialog(self, title, prompt, initialvalue=""):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.grab_set()

        label = ttk.Label(dialog, text=prompt)
        label.pack(pady=5)
        entry = ttk.Entry(dialog)
        entry.insert(0, initialvalue)
        entry.pack(pady=5, padx=10, fill=tk.X)
        entry.focus_set()

        result = {"value": None}

        def on_ok():
            result["value"] = entry.get()
            dialog.destroy()

        ok_btn = ttk.Button(dialog, text="OK", command=on_ok)
        ok_btn.pack(pady=5)
        dialog.bind("<Return>", lambda e: on_ok())

        self.root.wait_window(dialog)
        return result["value"]

    def setup_copy_functionality(self):
        """Enable copying from the log_text and console_text widgets."""
        # Bind Ctrl+C (and Cmd+C on macOS)
        self.log_text.bind("<Control-c>", self.copy_selection)
        self.log_text.bind("<Command-c>", self.copy_selection)  # macOS support
        self.console_text.bind("<Control-c>", self.copy_selection)
        self.console_text.bind("<Command-c>", self.copy_selection)
        
        # Create right-click context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Copy", command=self.copy_selection)
        
        # Bind right-click
        self.log_text.bind("<Button-3>", self.show_context_menu)  # Button-3 is right-click
        self.console_text.bind("<Button-3>", self.show_context_menu)

    def copy_selection(self, event=None):
        """Copy selected text to clipboard."""
        widget = event.widget if event else self.log_text
        try:
            selected_text = widget.selection_get()
            self.root.clipboard_clear()
            self.root.clipboard_append(selected_text)
            print("Text copied to clipboard")
            return "break"  # Prevent default bindings from interfering
        except tk.TclError:
            print("No text selected to copy")
            return "break"

    def show_context_menu(self, event):
        """Show right-click context menu at cursor position."""
        try:
            # Only show menu if text is selected
            if event.widget.selection_get():
                self.context_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass

    def run_system(self):
        """Run main.py in a separate thread."""
        print("Attempting to run system")
        if self.execution_thread and self.execution_thread.is_alive():
            messagebox.showinfo("Info", "System is already running. Please wait.")
            return
        
        self.run_button.config(state='disabled')
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, "Starting agent system...\n")
        self.log_text.config(state='disabled')
        self.console_text.config(state='normal')
        self.console_text.delete(1.0, tk.END)
        self.console_text.insert(tk.END, "Console ready.\n")
        self.console_text.config(state='disabled')
        
        # Clear previous outputs
        project_dir = os.path.join(os.getcwd(), "project")
        for folder in ["comms", "src", "tests"]:
            folder_path = os.path.join(project_dir, folder)
            if os.path.exists(folder_path):
                for file in glob.glob(os.path.join(folder_path, "*")):
                    try:
                        os.remove(file)
                    except OSError as e:
                        print(f"Error clearing file {file}: {e}")
        
        # Run main.py in a thread
        self.execution_thread = threading.Thread(target=self.execute_main)
        self.execution_thread.daemon = True
        self.execution_thread.start()

    def execute_main(self):
        """Execute main.py with output redirection."""
        try:
            main.main(self.output_queue, self.console_queue)
        except Exception as e:
            self.output_queue.put(f"Error: {str(e)}\n")
            print(f"Execution error: {e}", file=sys.stderr)
        finally:
            self.output_queue.put("--- Execution complete ---\n")
            self.root.after(0, lambda: self.run_button.config(state='normal'))

    def process_output_queue(self):
        """Process output queue and update log display."""
        if not self.running:
            return
        try:
            while True:
                message = self.output_queue.get_nowait()
                self.log_text.config(state='normal')
                self.log_text.insert(tk.END, message)
                self.log_text.see(tk.END)
                self.log_text.config(state='disabled')
        except queue.Empty:
            pass
        self.root.after(200, self.process_output_queue)

    def process_console_queue(self):
        """Process console queue and update console display."""
        if not self.running:
            return
        try:
            while True:
                message = self.console_queue.get_nowait()
                self.console_text.config(state='normal')
                self.console_text.insert(tk.END, message)
                self.console_text.see(tk.END)
                self.console_text.config(state='disabled')
        except queue.Empty:
            pass
        self.root.after(200, self.process_console_queue)

    def view_source_code(self):
        """Display generated source code in a new window."""
        print("Viewing source code")
        src_dir = os.path.join(os.getcwd(), "project", "src")
        if not os.path.exists(src_dir):
            messagebox.showinfo("Info", "No source code generated yet.")
            return
        
        code_window = tk.Toplevel(self.root)
        code_window.title("Source Code")
        code_window.geometry("400x300")
        
        text_area = scrolledtext.ScrolledText(code_window, height=15, width=50, wrap=tk.WORD)
        text_area.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        
        for file in glob.glob(os.path.join(src_dir, "*.py")):
            try:
                with open(file, "r") as f:
                    text_area.insert(tk.END, f"--- {os.path.basename(file)} ---\n")
                    text_area.insert(tk.END, f.read() + "\n\n")
            except OSError as e:
                text_area.insert(tk.END, f"Error reading {file}: {e}\n")
        
        text_area.config(state='disabled')

    def view_test_results(self):
        """Display test results in a new window."""
        print("Viewing test results")
        result_file = os.path.join(os.getcwd(), "project", "tests", "test_result.txt")
        if not os.path.exists(result_file):
            messagebox.showinfo("Info", "No test results available yet.")
            return
        
        result_window = tk.Toplevel(self.root)
        result_window.title("Test Results")
        result_window.geometry("400x200")
        
        text_area = scrolledtext.ScrolledText(result_window, height=10, width=50, wrap=tk.WORD)
        text_area.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        
        try:
            with open(result_file, "r") as f:
                text_area.insert(tk.END, f.read())
        except OSError as e:
            text_area.insert(tk.END, f"Error reading {result_file}: {e}\n")
        
        text_area.config(state='disabled')

    def create_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # GPU/CPU indicator
        self.hw_var = tk.StringVar()
        self.hw_var.set(self.get_hw_status())
        self.hw_label = ttk.Label(self.root, textvariable=self.hw_var, relief=tk.SUNKEN, anchor='e', width=10)
        self.hw_label.pack(side=tk.RIGHT)

    def set_status(self, message):
        self.status_var.set(message)

    def destroy(self):
        """Clean up on window close."""
        self.running = False
        if self.execution_thread and self.execution_thread.is_alive():
            print("Waiting for execution thread to finish")
        self.root.destroy()

    def create_llm_tab(self):
        label = ttk.Label(self.llm_frame, text="LLM Interaction Area", font=("Arial", 12))
        label.pack(pady=10)

        # LLM Selector
        llm_selector_frame = ttk.Frame(self.llm_frame)
        llm_selector_frame.pack(pady=5, padx=10, fill=tk.X)

        ttk.Label(llm_selector_frame, text="Select LLM:").pack(side=tk.LEFT, padx=(0, 5))
        self.llm_options = ["GPT-4", "Llama-3", "Custom-LLM"]  # Example LLMs
        self.llm_var = tk.StringVar(value=self.llm_options[0])
        llm_dropdown = ttk.Combobox(llm_selector_frame, textvariable=self.llm_var, values=self.llm_options, state="readonly", width=15)
        llm_dropdown.pack(side=tk.LEFT, padx=(0, 15))

        # Local/Cloud Selector
        ttk.Label(llm_selector_frame, text="Mode:").pack(side=tk.LEFT, padx=(0, 5))
        self.llm_mode_options = ["Local", "Cloud"]
        self.llm_mode_var = tk.StringVar(value=self.llm_mode_options[0])
        llm_mode_dropdown = ttk.Combobox(llm_selector_frame, textvariable=self.llm_mode_var, values=self.llm_mode_options, state="readonly", width=8)
        llm_mode_dropdown.pack(side=tk.LEFT)
        llm_mode_dropdown.bind("<<ComboboxSelected>>", self.on_llm_mode_change)

        # Cloud API key frame (hidden by default)
        self.llm_cloud_frame = ttk.Frame(self.llm_frame)
        self.llm_cloud_frame.pack(pady=5, padx=10, fill=tk.X)
        self.llm_cloud_frame.pack_forget()  # Hide initially

        ttk.Label(self.llm_cloud_frame, text="API Key:").pack(side=tk.LEFT, padx=(0, 5))
        self.llm_api_key_var = tk.StringVar()
        self.llm_api_key_entry = ttk.Entry(self.llm_cloud_frame, textvariable=self.llm_api_key_var, width=30)
        self.llm_api_key_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Link to get API key
        self.llm_api_link = ttk.Label(self.llm_cloud_frame, text="Get an API key", foreground="blue", cursor="hand2")
        self.llm_api_link.pack(side=tk.LEFT)
        self.llm_api_link.bind("<Button-1>", lambda e: self.open_api_key_link())

        self.llm_text = scrolledtext.ScrolledText(self.llm_frame, height=10, width=60, wrap=tk.WORD)
        self.llm_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.llm_entry = ttk.Entry(self.llm_frame, width=50)
        self.llm_entry.pack(padx=10, pady=5, side=tk.LEFT, fill=tk.X, expand=True)

        send_btn = ttk.Button(self.llm_frame, text="Send", command=self.llm_send)
        send_btn.pack(padx=5, pady=5, side=tk.LEFT)

    def on_llm_mode_change(self, event=None):
        mode = self.llm_mode_var.get()
        if mode == "Cloud":
            self.llm_cloud_frame.pack(pady=5, padx=10, fill=tk.X)
        else:
            self.llm_cloud_frame.pack_forget()

    def llm_send(self):
        prompt = self.llm_entry.get()
        if prompt:
            self.llm_text.insert(tk.END, f"You: {prompt}\n")
            self.llm_entry.delete(0, tk.END)
            # Placeholder for LLM response
            self.llm_text.insert(tk.END, "LLM: [response goes here]\n")
            self.llm_text.see(tk.END)

    def open_api_key_link(self):
        import webbrowser
        # You can customize this link as needed
        webbrowser.open_new("https://platform.openai.com/signup")

    def get_hw_status(self):
        if TORCH_AVAILABLE:
            return "GPU" if torch.cuda.is_available() else "CPU"
        else:
            return "CPU"

    def update_hw_status(self):
        """Update the hardware status label."""
        self.hw_var.set(self.get_hw_status())
        # Check again after 2 seconds
        if self.running:
            self.root.after(2000, self.update_hw_status)

    def create_chat_tab(self):
        """Create a simple chat tab with a text area and entry box."""
        label = ttk.Label(self.chat_frame, text="Chat Area", font=("Arial", 12))
        label.pack(pady=10)

        self.chat_text = scrolledtext.ScrolledText(self.chat_frame, height=10, width=60, wrap=tk.WORD, state='disabled')
        self.chat_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.chat_entry = ttk.Entry(self.chat_frame, width=50)
        self.chat_entry.pack(padx=10, pady=5, side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_entry.bind("<Return>", self.chat_send)

        send_btn = ttk.Button(self.chat_frame, text="Send", command=self.chat_send)
        send_btn.pack(padx=5, pady=5, side=tk.LEFT)

    def chat_send(self, event=None):
        """Handle sending a chat message."""
        message = self.chat_entry.get()
        if message:
            self.chat_text.config(state='normal')
            self.chat_text.insert(tk.END, f"You: {message}\n")
            self.chat_text.config(state='disabled')
            self.chat_entry.delete(0, tk.END)
            self.chat_text.see(tk.END)
            # Placeholder for bot response
            self.chat_text.config(state='normal')
            self.chat_text.insert(tk.END, "Bot: [response goes here]\n")
            self.chat_text.config(state='disabled')
            self.chat_text.see(tk.END)

def run_gui():
    root = tk.Tk()
    app = AgentSystemGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.destroy)
    root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent System CLI")
    parser.add_argument('command', choices=['run', 'view-code', 'view-tests', 'gui'], default='gui', nargs='?', help="Command to execute (default: gui)")
    args = parser.parse_args()

    if args.command == 'gui':
        run_gui()
    elif args.command == 'run':
        # Clear previous outputs (like in run_system)
        project_dir = os.path.join(os.getcwd(), "project")
        for folder in ["comms", "src", "tests"]:
            folder_path = os.path.join(project_dir, folder)
            if os.path.exists(folder_path):
                for file in glob.glob(os.path.join(folder_path, "*")):
                    try:
                        os.remove(file)
                    except OSError as e:
                        print(f"Error clearing file {file}: {e}")
        
        # Run the main logic without queues (uses console prints)
        print("Starting agent system...")
        main.main()  # No queues, so output goes to stdout
        print("--- Execution complete ---")
    elif args.command == 'view-code':
        src_dir = os.path.join(os.getcwd(), "project", "src")
        if not os.path.exists(src_dir):
            print("No source code generated yet.")
        else:
            for file in glob.glob(os.path.join(src_dir, "*.py")):
                try:
                    with open(file, "r") as f:
                        print(f"--- {os.path.basename(file)} ---")
                        print(f.read())
                        print("\n")
                except OSError as e:
                    print(f"Error reading {file}: {e}")
    elif args.command == 'view-tests':
        result_file = os.path.join(os.getcwd(), "project", "tests", "test_result.txt")
        if not os.path.exists(result_file):
            print("No test results available yet.")
        else:
            try:
                with open(result_file, "r") as f:
                    print(f.read())
            except OSError as e:
                print(f"Error reading {result_file}: {e}")

