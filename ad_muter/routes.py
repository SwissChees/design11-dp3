import os
import base64
import subprocess
from flask import render_template, jsonify, request, send_file
import threading

def register_routes(app, app_state, detection_loop):

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/status')
    def get_status():
        return jsonify(app_state)
        
    @app.route('/template_image')
    def template_image():
        if os.path.exists("scoreboard_template.png"):
            return send_file("scoreboard_template.png", mimetype='image/png')
        return "No template saved yet.", 404

    @app.route('/start', methods=['POST'])
    def start_bot():
        if not app_state["running"]:
            app_state["running"] = True
            threading.Thread(target=detection_loop, daemon=True).start()
        return jsonify({"status": "started"})

    @app.route('/stop', methods=['POST'])
    def stop_bot():
        app_state["running"] = False
        return jsonify({"status": "stopped"})

    @app.route('/update_settings', methods=['POST'])
    def update_settings():
        data = request.json
        if 'threshold' in data: app_state["threshold"] = float(data['threshold'])
        if 'grace_period' in data: app_state["grace_period"] = float(data['grace_period'])
        if 'ad_action' in data: app_state["ad_action"] = data['ad_action']
        if 'app_game' in data: app_state["app_game"] = data['app_game']
        if 'app_game_tab' in data: app_state["app_game_tab"] = data['app_game_tab']
        if 'app_ad' in data: app_state["app_ad"] = data['app_ad']
        if 'app_ad_tab' in data: app_state["app_ad_tab"] = data['app_ad_tab']
        return jsonify({"status": "updated"})

    # --- NEW: DYNAMIC APP & TAB FETCHING ---
    @app.route('/get_open_apps', methods=['GET'])
    def get_open_apps():
        try:
            # Asks macOS for a list of all apps currently running with a visible window
            script = """
            set AppleScript's text item delimiters to "|||"
            tell application "System Events"
                set appList to name of every application process whose background only is false
            end tell
            return appList as text
            """
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            apps = [app.strip() for app in result.stdout.split('|||') if app.strip()]
            apps = sorted(list(set(apps))) # Remove duplicates and sort alphabetically
            return jsonify({"apps": apps})
        except Exception as e:
            return jsonify({"apps": ["Error fetching apps"]})

    @app.route('/get_browser_tabs', methods=['POST'])
    def get_browser_tabs():
        app_name = request.json.get('app_name', '').strip()
        supported_browsers = ["google chrome", "safari", "brave browser", "microsoft edge"]
        
        if app_name.lower() not in supported_browsers:
            return jsonify({"tabs": []}) # Return empty if it's not a browser

        try:
            # Different browsers use slightly different AppleScript dictionaries
            tab_prop = "name" if app_name.lower() == "safari" else "title"
            
            script = f"""
            set AppleScript's text item delimiters to "|||"
            tell application "{app_name}"
                set tabList to {{}}
                repeat with w in windows
                    try
                        repeat with t in tabs of w
                            set end of tabList to {tab_prop} of t
                        end repeat
                    end try
                end repeat
                return tabList as text
            end tell
            """
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            tabs = [tab.strip() for tab in result.stdout.split('|||') if tab.strip()]
            return jsonify({"tabs": tabs})
        except Exception as e:
            return jsonify({"tabs": ["Error fetching tabs (Check Automation Permissions)"]})

    @app.route('/save_template', methods=['POST'])
    def save_template():
        try:
            data = request.json
            image_data = data.get('image_data')
            if not image_data: return jsonify({"error": "No image data provided"}), 400
            header, encoded = image_data.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            with open("scoreboard_template.png", "wb") as f: f.write(image_bytes)
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"Error saving template: {e}")
            return jsonify({"error": str(e)}), 500