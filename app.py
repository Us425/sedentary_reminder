import time
import ctypes
import tkinter as tk
from tkinter import ttk
import json
from tkinter import messagebox
import threading
import atexit

# Attempt to import pywin32 modules
try:
    import win32con
    import win32api
    import win32gui
    import win32ts
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("pywin32 library not found. Windows session event listener will be disabled.")

# pystray and PIL
try:
    from pystray import Icon as SysTrayIcon, Menu as SysTrayMenu, MenuItem as SysTrayMenuItem
    from PIL import Image
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    print("pystray or Pillow library not found. System tray icon will be disabled.")


# Main application file

# --- Global Variables ---
current_app_settings = {} 
global_main_timer = None
tray_icon_instance = None # Holds the pystray.Icon instance
is_timer_paused = False    # Manages pause/resume state for the tray menu
root_tk_instance = None    # Main Tkinter root instance, initialized in main
settings_window_instance = None # To keep track of the Toplevel settings window

SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "screen_lock_interval": 60,
    "enable_snooze": True,
    "num_snoozes": 3,
    "snooze_duration": 5
}

class Timer:
    """
    A simple countdown timer class.
    """
    def __init__(self, duration_seconds, settings, is_snooze_timer=False):
        self.duration_seconds = duration_seconds
        self.settings = settings
        self.is_snooze_timer = is_snooze_timer
        self.is_running = False
        self.should_stop = False
        
        if not self.is_snooze_timer:
            self.snoozes_left_session = self.settings.get("num_snoozes", DEFAULT_SETTINGS["num_snoozes"])

    def start(self):
        if self.is_running:
            print("Timer is already running.")
            return

        self.is_running = True
        self.should_stop = False
        print(f"Timer started for {self.duration_seconds} seconds. Snooze timer: {self.is_snooze_timer}")
        
        root_for_dialog = None
        if not tk._default_root and not root_tk_instance: # Fallback if no global root_tk_instance yet
             # This situation should be rare if root_tk_instance is initialized early in main
            if threading.current_thread() is threading.main_thread():
                 root_for_dialog = tk.Tk()
                 root_for_dialog.withdraw()
            else:
                # Cannot safely create Tk() from non-main thread without main loop running.
                # Postpone dialog creation or use a thread-safe queue to main thread.
                print("Warning: Cannot create dialog from non-main thread without Tk main loop.")


        for i in range(self.duration_seconds, 0, -1):
            if self.should_stop:
                print(f"Timer (snooze: {self.is_snooze_timer}) stopped prematurely.")
                self.is_running = False
                if root_for_dialog: root_for_dialog.destroy()
                return
            # print(f"Time remaining: {i} seconds") # Reduce console spam
            time.sleep(1)
        
        self.is_running = False
        if root_for_dialog: root_for_dialog.destroy()

        if not self.should_stop:
            self.on_timer_expire()
        else:
            print(f"Timer (snooze: {self.is_snooze_timer}) finished due to stop signal.")

    def stop(self):
        print(f"Stopping timer (snooze: {self.is_snooze_timer}). Is running: {self.is_running}")
        self.should_stop = True

    def on_timer_expire(self):
        global current_app_settings, root_tk_instance

        if self.is_snooze_timer:
            print("Snooze timer expired! Locking screen.")
            lock_screen()
        else:
            print("Main timer expired!")
            snooze_enabled = self.settings.get("enable_snooze", DEFAULT_SETTINGS["enable_snooze"])
            snooze_duration_minutes = self.settings.get("snooze_duration", DEFAULT_SETTINGS["snooze_duration"])

            if snooze_enabled and self.snoozes_left_session > 0:
                def ask_snooze_dialog():
                    user_response = messagebox.askyesno("Snooze?", 
                                       f"Your screen is about to lock. Snooze for {snooze_duration_minutes} minutes?",
                                       default=messagebox.NO)
                    if user_response:
                        print(f"User chose to snooze. Snoozes left: {self.snoozes_left_session - 1}")
                        self.snoozes_left_session -= 1
                        snooze_timer_duration_seconds = snooze_duration_minutes * 60
                        snooze_timer = Timer(snooze_timer_duration_seconds, self.settings, is_snooze_timer=True)
                        snooze_timer.start()
                    else:
                        print("User chose not to snooze. Locking screen.")
                        lock_screen()
                
                if root_tk_instance: # Use the main Tkinter instance if available
                    root_tk_instance.after(0, ask_snooze_dialog)
                else: # Fallback if no global root_tk_instance (e.g. during early startup or test)
                    if threading.current_thread() is threading.main_thread():
                        ask_snooze_dialog() # Safe to call directly
                    else:
                        # This is tricky. Ideally, queue this for the main thread.
                        # For now, print warning. Application should have root_tk_instance.
                        print("Warning: Cannot show snooze dialog from non-main thread without root_tk_instance.after")
                        lock_screen() # Default to locking if dialog cannot be shown.

            else: # Snooze not enabled or no snoozes left
                if not snooze_enabled: print("Snooze is disabled. Locking screen.")
                elif self.snoozes_left_session <= 0: print("No snoozes left. Locking screen.")
                lock_screen()

def lock_screen():
    try:
        ctypes.windll.user32.LockWorkStation()
        print("Screen locked successfully.")
    except AttributeError:
        print("Failed to lock screen. This function is intended for Windows.")
    except Exception as e:
        print(f"An unexpected error occurred while trying to lock the screen: {e}")

def reset_main_timer_and_snoozes():
    global global_main_timer, current_app_settings
    print("Attempting to reset main timer and snoozes...")
    if global_main_timer and global_main_timer.is_running:
        global_main_timer.stop()
        time.sleep(0.1) 
    loaded_settings = get_initial_settings() 
    new_main_timer_duration_seconds = loaded_settings.get("screen_lock_interval", DEFAULT_SETTINGS["screen_lock_interval"]) * 60
    if new_main_timer_duration_seconds <= 0:
        print("Screen lock interval is zero or negative. Timer will not start.")
        global_main_timer = None
        return
    print(f"Starting new main timer with duration: {new_main_timer_duration_seconds // 60} mins.")
    global_main_timer = Timer(duration_seconds=new_main_timer_duration_seconds, settings=loaded_settings)
    # Run the timer start in a new thread to prevent blocking if called from main thread that needs to do other things.
    # However, Timer itself uses time.sleep, so it's already blocking its own execution path.
    # If reset_main_timer_and_snoozes is called from a non-main thread (like Windows event listener),
    # starting another thread here is fine. If called from main thread, direct start is also fine.
    threading.Thread(target=global_main_timer.start, daemon=True).start()
    print("New main timer started.")

def save_settings(screen_lock_interval_var, enable_snooze_var, num_snoozes_var, snooze_duration_var):
    global current_app_settings
    try:
        settings_values = {
            "screen_lock_interval": int(screen_lock_interval_var.get()),
            "enable_snooze": enable_snooze_var.get(),
            "num_snoozes": int(num_snoozes_var.get()),
            "snooze_duration": int(snooze_duration_var.get())
        }
        if settings_values["screen_lock_interval"] <= 0: raise ValueError("Screen lock interval must be positive.")
        if settings_values["num_snoozes"] < 0: raise ValueError("Number of snoozes cannot be negative.")
        if settings_values["snooze_duration"] <= 0 and settings_values["enable_snooze"]:
            raise ValueError("Snooze duration must be positive if snooze is enabled.")
        with open(SETTINGS_FILE, 'w') as f: json.dump(settings_values, f, indent=4)
        current_app_settings = settings_values.copy()
        messagebox.showinfo("Settings Saved", "Settings saved successfully!")
    except ValueError as ve: messagebox.showerror("Input Error", f"Invalid input: {ve}")
    except Exception as e: messagebox.showerror("Error Saving Settings", f"An error occurred: {e}")

def load_settings_into_gui(screen_lock_interval_var, enable_snooze_var, num_snoozes_var, snooze_duration_var):
    global current_app_settings
    loaded_settings = DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, 'r') as f: loaded_settings.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        try:
            with open(SETTINGS_FILE, 'w') as f: json.dump(loaded_settings, f, indent=4)
        except Exception: pass # Ignore error saving default if file was just missing
    except Exception as e:
        messagebox.showerror("Error Loading Settings", f"Could not load settings: {e}\nLoading default values.")
    screen_lock_interval_var.set(str(loaded_settings["screen_lock_interval"]))
    enable_snooze_var.set(bool(loaded_settings["enable_snooze"]))
    num_snoozes_var.set(str(loaded_settings["num_snoozes"]))
    snooze_duration_var.set(str(loaded_settings["snooze_duration"]))
    current_app_settings = loaded_settings.copy()
    return loaded_settings

def show_settings_window():
    global root_tk_instance, settings_window_instance
    if not root_tk_instance:
        print("Error: Root Tkinter instance not initialized.")
        return
    if settings_window_instance and settings_window_instance.winfo_exists():
        settings_window_instance.deiconify()
        settings_window_instance.lift()
        settings_window_instance.focus_set()
        return
    settings_window = tk.Toplevel(root_tk_instance)
    settings_window.title("Settings")
    settings_window_instance = settings_window
    def on_settings_close_protocol():
        global settings_window_instance
        if settings_window_instance: settings_window_instance.destroy()
        settings_window_instance = None
    settings_window.protocol("WM_DELETE_WINDOW", on_settings_close_protocol)
    main_frame = ttk.Frame(settings_window, padding="10 10 10 10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    screen_lock_interval_var = tk.StringVar()
    enable_snooze_var = tk.BooleanVar()
    num_snoozes_var = tk.StringVar()
    snooze_duration_var = tk.StringVar()
    ttk.Label(main_frame, text="Screen Lock Interval (minutes):").grid(row=0, column=0, sticky=tk.W, pady=5)
    ttk.Entry(main_frame, textvariable=screen_lock_interval_var, width=10).grid(row=0, column=1, sticky=tk.E, pady=5)
    ttk.Checkbutton(main_frame, text="Enable Snooze Feature", variable=enable_snooze_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
    ttk.Label(main_frame, text="Number of Snoozes Allowed:").grid(row=2, column=0, sticky=tk.W, pady=5)
    ttk.Entry(main_frame, textvariable=num_snoozes_var, width=10).grid(row=2, column=1, sticky=tk.E, pady=5)
    ttk.Label(main_frame, text="Snooze Duration (minutes):").grid(row=3, column=0, sticky=tk.W, pady=5)
    ttk.Entry(main_frame, textvariable=snooze_duration_var, width=10).grid(row=3, column=1, sticky=tk.E, pady=5)
    load_settings_into_gui(screen_lock_interval_var, enable_snooze_var, num_snoozes_var, snooze_duration_var)
    save_button = ttk.Button(main_frame, text="Save Settings", 
                             command=lambda: save_settings(screen_lock_interval_var, enable_snooze_var, num_snoozes_var, snooze_duration_var))
    save_button.grid(row=4, column=0, columnspan=2, pady=10)
    settings_window.deiconify()

# --- System Tray Icon Functions ---
def create_placeholder_icon_image():
    if not PYSTRAY_AVAILABLE: return None
    image = Image.new('RGB', (64, 64), color='red')
    # You could add more details to the image if desired, e.g., a letter
    # from PIL import ImageDraw
    # draw = ImageDraw.Draw(image)
    # draw.text((10,10), "SLT", fill=(255,255,0)) # Example text
    return image

def get_pause_resume_text():
    return "Resume Timer" if is_timer_paused else "Pause Timer"

def on_show_settings_clicked():
    global root_tk_instance
    print("Tray: Show Settings clicked.")
    if root_tk_instance:
        root_tk_instance.after(0, show_settings_window)
    else:
        print("Error: root_tk_instance not available.")

def on_toggle_pause_resume_clicked():
    global is_timer_paused, global_main_timer, tray_icon_instance
    is_timer_paused = not is_timer_paused
    print(f"Tray: Toggle Pause/Resume. New state: {'Paused' if is_timer_paused else 'Running'}")
    if is_timer_paused:
        if global_main_timer and global_main_timer.is_running:
            global_main_timer.stop()
            print("Timer paused.")
    else:
        print("Resuming timer (by resetting)...")
        reset_main_timer_and_snoozes() # This restarts the timer
    if tray_icon_instance: # pystray requires menu update for text change
        tray_icon_instance.update_menu()

def on_exit_clicked():
    global tray_icon_instance, root_tk_instance, global_main_timer
    print("Tray: Exit clicked. Cleaning up...")
    if global_main_timer: global_main_timer.stop()
    if tray_icon_instance: tray_icon_instance.stop()
    if root_tk_instance: root_tk_instance.destroy() # Use destroy for cleaner exit
    # atexit handles WTSUnRegisterSessionNotification
    print("Cleanup initiated. Application should exit.")

def run_tray_icon():
    global tray_icon_instance, PYSTRAY_AVAILABLE
    if not PYSTRAY_AVAILABLE:
        print("pystray/Pillow not available. Tray icon cannot run.")
        return
    icon_image = create_placeholder_icon_image()
    if not icon_image:
        print("Failed to create icon image for tray.")
        return
    menu = SysTrayMenu(
        SysTrayMenuItem('Show Settings', on_show_settings_clicked),
        SysTrayMenuItem(get_pause_resume_text, on_toggle_pause_resume_clicked, enabled=True), # Text is callable
        SysTrayMenuItem('Exit', on_exit_clicked)
    )
    tray_icon_instance = SysTrayIcon("ScreenLockTimer", icon_image, "Screen Lock Timer", menu)
    print("Starting pystray icon...")
    try:
        tray_icon_instance.run() # This blocks the thread it runs in
    except Exception as e:
        print(f"Error in pystray icon.run(): {e}")
    finally:
        print("pystray icon.run() finished.")

# --- Windows Session Event Listener ---
WNDPROC_CLASS_NAME = "ScreenLockTimerWindowClass"
WM_WTSSESSION_CHANGE = 0x02B1
if PYWIN32_AVAILABLE and not hasattr(win32con, 'WTS_SESSION_UNLOCK'):
    win32con.WTS_SESSION_UNLOCK = 0x8

def wndproc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    elif msg == WM_WTSSESSION_CHANGE:
        if wparam == win32con.WTS_SESSION_UNLOCK:
            print("Session unlocked. Resetting main timer via event listener.")
            # Schedule reset_main_timer_and_snoozes in main thread if it involves Tkinter directly
            # or ensure it's thread-safe. For now, direct call as it mostly manages timer object.
            # Timer's on_timer_expire uses root_tk_instance.after for dialogs.
            reset_main_timer_and_snoozes()
        elif wparam == getattr(win32con, 'WTS_SESSION_LOCK', 0x7): # Check if WTS_SESSION_LOCK exists
             print("Session locked via event listener.")
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def windows_event_listener():
    if not PYWIN32_AVAILABLE: return
    print("Starting Windows event listener thread...")
    wc = win32gui.WNDCLASS()
    wc.hInstance = win32api.GetModuleHandle(None)
    wc.lpszClassName = WNDPROC_CLASS_NAME
    wc.lpfnWndProc = wndproc
    try:
        class_atom = win32gui.RegisterClass(wc)
        hwnd = win32gui.CreateWindowEx(0, class_atom, "ScreenLockTimerHiddenWindow", 0, 0, 0, 0, 0, 0, wc.hInstance, None)
        if not hwnd:
            print(f"Failed to create hidden window. Error: {win32api.GetLastError()}")
            return
        if win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION):
            atexit.register(win32ts.WTSUnRegisterSessionNotification, hwnd)
            print("Successfully registered for session notifications.")
        else:
            print(f"Failed to register session notification. Error: {win32api.GetLastError()}")
            win32gui.DestroyWindow(hwnd) # Clean up window if registration fails
            win32gui.UnregisterClass(class_atom, wc.hInstance) # Clean up class
            return
        win32gui.PumpMessages()
    except Exception as e:
        print(f"Error in Windows event listener: {e}")
    finally:
        if 'hwnd' in locals() and hwnd: # Check if hwnd was created
             try: win32gui.DestroyWindow(hwnd)
             except Exception: pass
        if 'class_atom' in locals() and class_atom: # Check if class_atom was registered
             try: win32gui.UnregisterClass(class_atom, wc.hInstance)
             except Exception: pass
        print("Windows event listener thread finished.")

# --- Main Application Execution ---
def get_initial_settings():
    global current_app_settings
    s = DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, 'r') as f: s.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        try:
            with open(SETTINGS_FILE, 'w') as f: json.dump(s, f, indent=4)
        except Exception: pass
    except Exception as e_load: print(f"Error loading settings: {e_load}. Using defaults.")
    current_app_settings = s.copy()
    return s

if __name__ == "__main__":
    root_tk_instance = tk.Tk()
    root_tk_instance.withdraw()

    initial_settings = get_initial_settings()
    if not current_app_settings: get_initial_settings() # Ensure settings are loaded

    print(f"\nInitial call to start/reset main timer with settings: {current_app_settings}")
    reset_main_timer_and_snoozes()

    if PYWIN32_AVAILABLE:
        win_listener_thread = threading.Thread(target=windows_event_listener, daemon=True)
        win_listener_thread.name = "WinEventListenerThread"
        win_listener_thread.start()
    else:
        print("Skipping Windows event listener (pywin32 missing).")
        
    tray_thread = None
    if PYSTRAY_AVAILABLE:
        # pystray's run() is blocking, so it needs its own thread.
        # It should not be a daemon if we want it to keep the app alive in absence of Tkinter mainloop.
        # However, with Tkinter mainloop, it can be daemon. Let's make it non-daemon for robustness.
        tray_thread = threading.Thread(target=run_tray_icon, daemon=False) 
        tray_thread.name = "SysTrayThread"
        tray_thread.start()
    else:
        print("Skipping system tray icon (pystray/Pillow missing).")
        print("Application will run without tray icon. Close console to exit.")
        # If no tray, and we want to show settings, we'd need to call:
        # root_tk_instance.after(100, show_settings_window) # Example: show settings after short delay

    print("Application setup complete. Running Tkinter main loop.")
    try:
        root_tk_instance.mainloop()
    except KeyboardInterrupt:
        print("Tkinter mainloop interrupted by user (Ctrl+C).")
    finally:
        print("Tkinter mainloop finished.")
        # Mainloop finished, try to clean up tray if it's still running
        if PYSTRAY_AVAILABLE and tray_icon_instance and tray_icon_instance.visible:
            print("Attempting to stop tray icon as Tkinter mainloop finished...")
            tray_icon_instance.stop() # Signal pystray to stop
        if tray_thread and tray_thread.is_alive():
            tray_thread.join(timeout=2) # Wait for tray thread to finish
            if tray_thread.is_alive():
                 print("Warning: Tray thread did not exit cleanly.")
        
    print("Application exiting.")
