import time
import threading
import os
import json
import psutil
import platform
import tkinter as tk
from tkinter import simpledialog, messagebox

# ---------------- OS and Sound ----------------
IS_WINDOWS = platform.system().lower().startswith("win")
if IS_WINDOWS:
    import winsound

CONFIG_FILE = "battery_config.json"

# ---------------- Config Handling ----------------
def load_config():
    """Load saved high/low levels from JSON or create default."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Validate loaded config
                if validate_config(config):
                    return config
        except (json.JSONDecodeError, KeyError):
            print("⚠ Config file corrupted, creating new one...")
    # default values
    return {"high": 90, "low": 20}

def validate_config(config):
    """Validate that config has proper high/low values."""
    return (isinstance(config, dict) and 
            "high" in config and "low" in config and
            50 <= config["high"] <= 100 and 
            1 <= config["low"] <= 89 and
            config["low"] < config["high"] - 10)

def save_config(data):
    """Save high/low thresholds to JSON."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)

# ---------------- Ask user for thresholds ----------------
def ask_levels():
    """Ask user for battery high/low levels with validation."""
    root = tk.Tk()
    root.title("Battery Monitor Setup")
    root.withdraw()
    
    while True:
        high = simpledialog.askinteger(
            "Set High Battery Level",
            "Enter HIGH battery % (50-100):\n(Alert when charged above this level)",
            initialvalue=90,
            minvalue=50, 
            maxvalue=100
        )
        if high is None:  # User cancelled
            root.destroy()
            return load_config()
        
        low = simpledialog.askinteger(
            "Set Low Battery Level", 
            "Enter LOW battery % (1-89):\n(Alert when battery drops below this level)",
            initialvalue=20,
            minvalue=1, 
            maxvalue=89
        )
        if low is None:  # User cancelled
            root.destroy()
            return load_config()
        
        # Validate that low is significantly less than high
        # if low >= high - 0:
        #     messagebox.showerror(
        #         "Invalid Range", 
        #         f"Low level ({low}%) must be at least 5% lower than high level ({high}%).\nPlease try again."
        #     )
        else:
            break
    
    root.destroy()
    
    config = {"high": high, "low": low}
    save_config(config)
    
    messagebox.showinfo(
        "Settings Saved", 
        f"Battery monitoring configured:\n"
        f"• High Alert: {high}%\n"
        f"• Low Alert: {low}%\n\n"
        f"You can change these by deleting the '{CONFIG_FILE}' file."
    )
    
    return config

def ask_change_levels():
    """Ask user if they want to change levels at startup."""
    root = tk.Tk()
    root.withdraw()
    
    result = messagebox.askyesno(
        "Battery Monitor",
        "Would you like to change the battery alert levels?\n\n"
        f"Current settings:\nHigh: {load_config()['high']}% | Low: {load_config()['low']}%\n\n"
        "Click 'No' to continue with current settings."
    )
    root.destroy()
    
    return result

# ---------------- Fullscreen Alert ----------------
def show_fullscreen_alert(message, color):
    """Display a fullscreen colored alert with an OK button."""
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.configure(bg=color)
    root.attributes('-topmost', True)  # Always on top

    # Center content frame
    frame = tk.Frame(root, bg=color)
    frame.pack(expand=True)

    label = tk.Label(frame, text=message, font=("Arial", 45, "bold"),
                     fg="white", bg=color, wraplength=800)
    label.pack(pady=50)

    def on_ok():
        root.destroy()

    btn = tk.Button(frame, text="OK", font=("Arial", 25, "bold"),
                    command=on_ok, bg="white", fg="black", 
                    padx=30, pady=15, relief="raised", bd=3)
    btn.pack(pady=30)

    # Play sound when alert shows (not when OK is clicked)
    threading.Thread(target=play_sound, daemon=True).start()
    
    # Focus the window
    root.focus_force()
    
    root.mainloop()

# ---------------- Sound ----------------
def play_sound(duration=3):
    """Play beep sound for few seconds."""
    if IS_WINDOWS:
        for _ in range(duration * 2):
            winsound.Beep(1000, 400)
            time.sleep(0.3)
    else:
        for _ in range(duration * 2):
            print("\a", end="", flush=True)
            time.sleep(0.5)

# ---------------- Battery Status Display ----------------
def print_battery_status(batt, high_level, low_level):
    """Print current battery status with visual indicators."""
    percent = batt.percent
    plugged = batt.power_plugged
    status = "🔌 Plugged in" if plugged else "🔋 On battery"
    
    # Create a simple battery visualization
    bars = int(percent / 10)
    battery_bar = "[" + "█" * bars + " " * (10 - bars) + "]"
    
    # Color coding for terminal (approximate)
    if plugged and percent >= high_level:
        color_indicator = "🟥 FULL"
    elif not plugged and percent <= low_level:
        color_indicator = "🟦 LOW" 
    elif plugged:
        color_indicator = "🟩 CHARGING"
    else:
        color_indicator = "🟨 DISCHARGING"
    
    print(f"\r{battery_bar} {percent:.0f}% | {status} | {color_indicator} | Monitoring...", 
          end="", flush=True)

# ---------------- Main Monitor ----------------
def main():
    # Ask if user wants to change levels each time
    if ask_change_levels():
        config = ask_levels()
    else:
        config = load_config()

    high_level = config["high"]
    low_level = config["low"]

    print(f"\n🎯 Battery Monitor Started")
    print(f"⚡ High Alert: {high_level}% | 🔋 Low Alert: {low_level}%")
    print("Press Ctrl+C to stop monitoring\n")

    high_alerted = False
    low_alerted = False
    last_percent = None

    try:
        while True:
            batt = psutil.sensors_battery()
            if not batt:
                print("❌ Battery information not available.")
                return

            percent = batt.percent
            plugged = batt.power_plugged
            
            # Only print status if it changed
            if last_percent != percent:
                print_battery_status(batt, high_level, low_level)
                last_percent = percent

            # ⚠ High battery alert
            if plugged and percent >= high_level and not high_alerted:
                show_fullscreen_alert(
                    f"⚠ BATTERY FULL ⚠\n\n{percent:.0f}% Reached!\n\nPlease unplug charger", 
                    "red"
                )
                high_alerted = True
                low_alerted = False
                print(f"\n🔔 HIGH ALERT TRIGGERED at {percent:.0f}%")

            # 🔋 Low battery alert
            elif not plugged and percent <= low_level and not low_alerted:
                show_fullscreen_alert(
                    f"⚠ BATTERY LOW ⚠\n\n{percent:.0f}% Remaining!\n\nPlease plug in charger", 
                    "blue"
                )
                low_alerted = True
                high_alerted = False
                print(f"\n🔔 LOW ALERT TRIGGERED at {percent:.0f}%")

            # 🔁 Reset alerts for next use
            if plugged and percent < high_level - 5:
                high_alerted = False
                print(f"\n🔄 High alert reset (battery at {percent:.0f}%)")
            if not plugged and percent > low_level + 5:
                low_alerted = False
                print(f"\n🔄 Low alert reset (battery at {percent:.0f}%)")

            time.sleep(30)  # check every 30 seconds

    except KeyboardInterrupt:
        print(f"\n\n⏹ Battery monitoring stopped.")
        print(f"💾 Settings saved: High={high_level}%, Low={low_level}%")

# ---------------- Run ----------------
if __name__ == "__main__":
    # If no config exists, ask user to set levels
    if not os.path.exists(CONFIG_FILE):
        print("🔧 First-time setup: Please configure battery levels")
        ask_levels()
    
    main()
