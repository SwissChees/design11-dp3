import sys
import time
import cv2
import numpy as np
import subprocess
from mss import mss
from flask import Flask

app = Flask(__name__)

# --- GLOBAL STATE & LOGGING ---
app_state = {
    "running": False,
    "muted": False,
    "status": "Idle",
    "logs": [],
    "live_match": 0.0,
    "threshold": 0.60, 
    "grace_period": 1.5, 
    "ad_action": "mute", 
    "app_game": "Google Chrome",
    "app_game_tab": "", 
    "app_ad": "Spotify",
    "app_ad_tab": ""    
}

def log_msg(msg):
    timestamp = time.strftime('%H:%M:%S')
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg) 
    app_state["logs"].append(full_msg)
    if len(app_state["logs"]) > 50:
        app_state["logs"].pop(0)

def is_muted():
    try:
        result = subprocess.run(
            ['osascript', '-e', 'output muted of (get volume settings)'], 
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip() == 'true'
    except subprocess.CalledProcessError:
        return False

def set_mute(mute_state, context=""):
    currently_muted = is_muted()
    app_state["status"] = context
    app_state["muted"] = mute_state
    
    if currently_muted != mute_state:
        state_str = "true" if mute_state else "false"
        subprocess.run(['osascript', '-e', f'set volume output muted {state_str}'])
        status = "MUTED" if mute_state else "UNMUTED"
        log_msg(f"Audio {status} - {context}")

# --- SYSTEM ACTIONS ---
black_process = None

def toggle_black_screen(show, monitor=None, target_rect=None):
    global black_process
    if show and black_process is None and monitor and target_rect:
        x, y, w, h = target_rect
        pad = 30 
        
        px = max(0, x - pad)
        py = max(0, y - pad)
        pw = w + pad * 2
        ph = h + pad * 2

        mw = monitor['width']
        mh = monitor['height']
        mx = monitor['left']
        my = monitor['top']

        script = f"""import tkinter as tk
r = tk.Tk()
r.withdraw()

def create_box(w, h, x, y):
    if w <= 0 or h <= 0: return
    win = tk.Toplevel()
    win.geometry(f"{{int(w)}}x{{int(h)}}+{{int(x)}}+{{int(y)}}")
    win.attributes('-topmost', True)
    win.overrideredirect(True)
    win.configure(bg='black')
    win.config(cursor='none')

create_box({mw}, {py}, {mx}, {my}) 
create_box({mw}, {mh - (py + ph)}, {mx}, {my + py + ph}) 
create_box({px}, {ph}, {mx}, {my + py}) 
create_box({mw - (px + pw)}, {ph}, {mx + px + pw}, {my + py}) 

r.mainloop()
"""
        black_process = subprocess.Popen([sys.executable, '-c', script])
        log_msg("Peephole Black Screen activated.")
        
    elif not show and black_process is not None:
        black_process.terminate()
        black_process = None
        log_msg("Black Screen removed.")

def switch_to_app_or_tab(app_name, tab_title=""):
    if not app_name or not app_name.strip(): return

    if tab_title.strip() and app_name.lower() in ["google chrome", "safari", "brave browser", "microsoft edge"]:
        script = f"""
        tell application "{app_name}"
            activate
            repeat with w in windows
                set i to 1
                repeat with t in tabs of w
                    if title of t contains "{tab_title}" then
                        set active tab index of w to i
                        set index of w to 1
                        return
                    end if
                    set i to i + 1
                end repeat
            end repeat
        end tell
        """
        try:
            subprocess.run(['osascript', '-e', script])
            log_msg(f"Switched to Tab: '{tab_title}' in {app_name}")
        except Exception as e:
            log_msg(f"Failed to switch tab: {e}")
    else:
        try:
            subprocess.run(['osascript', '-e', f'tell application "{app_name}" to activate'])
            log_msg(f"Switched context to: {app_name}")
        except Exception as e:
            log_msg(f"Failed to switch app: {e}")

# --- UPDATED: SPATIAL FREQUENCY EXTRACTION ---
def extract_transparent_logo(gray_img):
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
    enhanced = clahe.apply(gray_img)
    
    # NEW: Increased Gaussian Kernel to (5,5). 
    # This aggressively melts away "dirty" background textures (faces, crowds, ice lines)
    # but leaves the thick, structural logo edges completely intact for the Sobel filter.
    blur = cv2.GaussianBlur(enhanced, (5, 5), 0)
    
    sobelx = cv2.Sobel(blur, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(blur, cv2.CV_64F, 0, 1, ksize=3)
    mag = cv2.magnitude(sobelx, sobely)
    
    mag_8u = cv2.convertScaleAbs(mag, alpha=1.5)
    
    # NEW: Lowered Noise Floor. Because the larger blur destroyed the background noise,
    # we can safely drop this threshold from 60 to 40 to catch very faint logo traces.
    _, clean = cv2.threshold(mag_8u, 40, 255, cv2.THRESH_TOZERO)
    
    return clean

# --- PURE VISUAL DETECTION (LOCKED TARGET) ---
def detection_loop():
    template_path = "scoreboard_template.png"
    sct = mss()
    monitor = sct.monitors[1]
    
    base_template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if base_template is None:
        log_msg(f"Error: Could not load '{template_path}'. Please set up target first.")
        app_state["running"] = False
        return
        
    template_mask = extract_transparent_logo(base_template)
    
    scales = np.linspace(0.5, 2.0, 30) 
    scaled_templates = [
        cv2.resize(template_mask, (int(template_mask.shape[1]*s), int(template_mask.shape[0]*s))) 
        for s in scales if int(template_mask.shape[1]*s) >= 10 and int(template_mask.shape[0]*s) >= 10
    ]

    log_msg("Switch to your game now! Locking target in 3 seconds...")
    for i in range(3, 0, -1):
        if not app_state["running"]:  
            log_msg("Start aborted.")
            return
        log_msg(f"Locking in {i}...")
        time.sleep(1)

    log_msg("Scanning full screen to lock target coordinates...")

    screen_init = np.array(sct.grab(monitor))
    screen_gray_init = cv2.cvtColor(screen_init, cv2.COLOR_BGRA2GRAY)
    screen_mask_init = extract_transparent_logo(screen_gray_init)
    
    best_init_val = 0
    locked_rect = None
    locked_template = None
    
    for tmpl in scaled_templates:
        if tmpl.shape[0] > screen_mask_init.shape[0] or tmpl.shape[1] > screen_mask_init.shape[1]: 
            continue
        res = cv2.matchTemplate(screen_mask_init, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val > best_init_val:
            best_init_val = max_val
            locked_rect = (max_loc[0], max_loc[1], tmpl.shape[1], tmpl.shape[0])
            locked_template = tmpl
            
    adjusted_init_val = min(1.0, best_init_val * 1.8) 
    
    if adjusted_init_val < app_state["threshold"]:
        log_msg(f"Lock Failed! Could not find target (Best match: {adjusted_init_val*100:.1f}%).")
        app_state["running"] = False
        return
        
    log_msg(f"Target LOCKED at coordinates {locked_rect}.")
    
    lx, ly, lw, lh = locked_rect
    pad = 10 
    
    mon_h, mon_w = screen_gray_init.shape
    crop_y1 = max(0, ly - pad)
    crop_y2 = min(mon_h, ly + lh + pad)
    crop_x1 = max(0, lx - pad)
    crop_x2 = min(mon_w, lx + lw + pad)

    grab_region = {
        "top": monitor["top"] + crop_y1,
        "left": monitor["left"] + crop_x1,
        "width": crop_x2 - crop_x1,
        "height": crop_y2 - crop_y1
    }

    is_commercial_mode = False
    target_lost_time = None
    
    recovery_counter = 0 
    REQUIRED_RECOVERY_FRAMES = 4

    while app_state["running"]:
        try:
            screen_patch = np.array(sct.grab(grab_region))
            patch_gray = cv2.cvtColor(screen_patch, cv2.COLOR_BGRA2GRAY)
            
            # Use the new spatial frequency extractor directly on the live frame
            patch_mask = extract_transparent_logo(patch_gray)

            if cv2.countNonZero(patch_mask) < 20:
                highest_confidence = 0.0
            else:
                res = cv2.matchTemplate(patch_mask, locked_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                highest_confidence = min(1.0, max_val * 1.8) 

            found_target = (highest_confidence >= app_state["threshold"])
            app_state["live_match"] = highest_confidence

            if is_commercial_mode:
                if found_target:
                    recovery_counter += 1
                else:
                    recovery_counter = 0 
                
                print(f"Live Scan: {highest_confidence*100:.1f}% | Unmute Buffer: {recovery_counter}/{REQUIRED_RECOVERY_FRAMES}")

                if recovery_counter >= REQUIRED_RECOVERY_FRAMES:
                    is_commercial_mode = False
                    recovery_counter = 0 
                    set_mute(False, f"Game Returned! (Match: {highest_confidence*100:.1f}%)")
                    
                    if app_state["ad_action"] == "black":
                        toggle_black_screen(False)
                    elif app_state["ad_action"] == "switch":
                        switch_to_app_or_tab(app_state["app_game"], app_state["app_game_tab"])
                        
                    time.sleep(1.0) 

            else:
                print(f"Live Scan Confidence: {highest_confidence*100:.1f}% | Threshold: {app_state['threshold']*100:.1f}%")
                
                if found_target:
                    target_lost_time = None 
                else:
                    if target_lost_time is None:
                        target_lost_time = time.time()
                    
                    time_missing = time.time() - target_lost_time

                    if time_missing >= app_state["grace_period"]:
                        is_commercial_mode = True
                        set_mute(True, f"Target Lost -> Break Started")
                        
                        if app_state["ad_action"] == "black":
                            toggle_black_screen(True, monitor, locked_rect)
                        elif app_state["ad_action"] == "switch":
                            switch_to_app_or_tab(app_state["app_ad"], app_state["app_ad_tab"])

            time.sleep(0.1) 
                
        except Exception as e:
            log_msg(f"Error in loop: {e}")
            time.sleep(1)

    log_msg("Monitoring stopped. Cleaning up system states.")
    subprocess.run(['osascript', '-e', 'set volume output muted false'])
    toggle_black_screen(False)
    app_state["muted"] = False
    app_state["status"] = "Idle"

from routes import register_routes
register_routes(app, app_state, detection_loop)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)