# 🏈 Auto-Muter (Pure Visual Broadcast Tracker)

Auto-Muter is a lightweight, pure computer-vision application designed to automatically detect commercial breaks during live sports broadcasts and instantly mute your computer, black out the screen, or switch to a different app (like Spotify or Reddit). 

Unlike traditional methods that rely on unreliable audio spikes, this tool uses localized HDR and true 3D edge detection to track the broadcast network's transparent watermark logo. When the logo disappears, the commercial has started. When the logo returns, the game is back on.

---

## ✨ Key Features

* **100% Pure Visual Tracking:** Completely ignores system audio. It watches the screen via an ultra-fast localized capture loop (`mss`).
* **Transparent Logo Extraction:** Uses OpenCV Sobel math to calculate the "3D embossed" shape of a logo, allowing it to track highly transparent watermarks even when the camera pans from dark crowds to bright white ice.
* **The "Peephole" Blackout:** If you choose to black out your screen during an ad, the script dynamically draws 4 separate black borders that perfectly wrap *around* the logo. This prevents the Python script from blinding itself and ensures it knows exactly when the game returns.
* **App & Tab Switcher:** Native macOS AppleScript integration allows the bot to seamlessly yank a specific browser tab (e.g., ESPN) or app (e.g., Spotify) to the front during a commercial, and switch you back when the puck drops.
* **Debouncing & Recovery:** Requires the target to be mathematically verified for multiple consecutive frames before unmuting, preventing false positives from random commercials.
* **Local Web Dashboard:** A cohesive retro-themed UI to set your visual thresholds, grace periods, test macOS app connections, and crop your target image directly from your browser.

---

## 🛠 Prerequisites & Installation

**System Requirements:**
* **macOS is required.** This project heavily relies on macOS `osascript` (AppleScript) for muting the system volume, managing Tkinter blackout windows, and swapping active applications/tabs.
* **Python 3.8+**

**Installation:**
1. Clone the repository to your local machine.
2. Install the required Python packages using the provided `requirements.txt`:
   ```bash
   pip install -r requirements.txt
# Live Sports Commercial Detection Dashboard

> **Note:** The required packages are `flask`, `opencv-python`, `mss`, and `numpy`.

## 3. Run the Application

```bash
python app.py
```

### Important macOS Security Step

The first time you run this, macOS will prompt you to grant your Terminal/IDE **Screen Recording** and **Automation** permissions.

You must allow these permissions, or the script will not be able to see your screen or switch your apps.

---

## 🚀 How to Use: Step-by-Step

### 1. Launch the Dashboard

Start `app.py` in your terminal and navigate to:

```text
http://localhost:5001
```

in your web browser.

### 2. Prepare the Broadcast

Ensure your live sports broadcast is visible on your screen.

### 3. Capture the Target

Click:

```text
📸 SETUP TARGET
```

Your browser will ask to share your screen.

### 4. Draw the Bounding Box

Draw a tight box only around the transparent network logo, such as the `"TSN"` watermark.

Try to avoid capturing the game clock or shifting score numbers.

### 5. Save

Click:

```text
💾 SAVE TEMPLATE
```

### 6. Configure Behavior

Set the following options:

- **Visual Threshold**: default is `0.60`
- **Grace Period**: for example, `1.5 seconds`
- **On Commercial action**:
  - Mute Only
  - Black Screen
  - Switch App

### 7. Test Connections

If you are using app switching, use the dropdown menus to select:

- Your **Game App/Tab**
- Your **Ad Break App/Tab**

Then use the **Test Connection** buttons to verify macOS can locate them.

### 8. Start Monitoring

Click:

```text
▶ START GAME
```

---

## ⚠️ Important Note

For the App Switcher to work properly, your **Ad Break** application must not physically cover the corner of the screen where the broadcast logo lives.

Otherwise, the bot will go blind.

Keep windows side-by-side if necessary.

---

## 🧠 Core Architecture & How It Works

## 1. The Computer Vision Pipeline: `extract_transparent_logo`

Transparent watermarks are notoriously difficult to track because their pixel values constantly change based on the background video.

Standard template matching fails here.

Instead, the image is passed through a specialized math pipeline.

### CLAHE: Contrast Limited Adaptive Histogram Equalization

CLAHE acts as an extreme local HDR filter to balance the contrast.

### Sobel Filters

Sobel filters calculate the physical "slope" of the pixels to find true 3D edges while ignoring flat colors.

### Noise Floor

A heavy binary threshold deletes faint background textures, leaving only the sharp, glassy edges of the logo.

---

## 2. CPU Optimization: Target Lock

Doing complex Sobel math on a 1080p screen 30 times a second will heavily load the CPU.

The script solves this in two phases.

### Phase 1: Full-Screen Scan

The script performs one massive, full-screen scan to locate the exact `(X, Y)` coordinates of the logo.

### Phase 2: Locked Tiny Capture Region

After the logo is located, the script locks those coordinates and restricts the `mss` screenshot library to only photograph a tiny `50x50` pixel bounding box.

This allows the main loop to run very quickly while using minimal CPU.

---

## 3. The Debouncing State Machine

To prevent false positives, such as a car commercial flashing a white shape that accidentally looks like the logo for a fraction of a second, the state machine uses a `recovery_counter`.

The script requires the target to be mathematically verified for **4 consecutive frames** before it trusts the data, resets the state, and unmutes the system.

---

## 🛑 Troubleshooting & FAQs

## Why is the bot missing the logo?

Make sure your crop box is tight around the letters of the logo and does **not** include the game clock.

You can also try slightly lowering the **Visual Threshold** slider on the dashboard.

---

## Why is the bot unmuting during a commercial?

Make sure your **Visual Threshold** is not too low.

If the bot is picking up random shapes, raise the threshold to:

```text
0.70 or higher
```

Also ensure the **Grace Period** is high enough, usually:

```text
1.5s - 2.0s
```

This helps account for camera angle cuts during the game.

---
