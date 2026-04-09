"""AppleScript bindings — expose Sentinel to AppleScript/Automator."""
import subprocess
import json


def run_applescript(script: str) -> str:
    """Run an AppleScript and return output."""
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def display_dialog(text: str, title: str = "Sentinel", buttons: list = None) -> str:
    """Show an AppleScript dialog."""
    if buttons is None:
        buttons = ["OK"]
    btns = ",".join(f'"{b}"' for b in buttons[:3])
    script = (f'display dialog "{text}" with title "{title}" '
              f'buttons {{{btns}}} default button 1')
    result = run_applescript(script)
    return result


def get_user_input(prompt: str, default: str = "") -> str:
    """Prompt user for input via AppleScript."""
    script = (f'text returned of (display dialog "{prompt}" '
              f'default answer "{default}")')
    return run_applescript(script)


def choose_from_list(items: list, title: str = "Sentinel") -> str:
    """Show a list picker."""
    item_list = ",".join(f'"{i}"' for i in items)
    script = f'choose from list {{{item_list}}} with title "{title}"'
    return run_applescript(script)


def sentinel_applescript_api() -> str:
    """Generate an AppleScript snippet for calling Sentinel via curl."""
    return '''on sentinelCall(endpoint, method, jsonBody)
    set baseUrl to "http://localhost:9849"
    set fullUrl to baseUrl & endpoint
    if method is "GET" then
        return do shell script "curl -s " & fullUrl
    else
        return do shell script "curl -s -X " & method & " -H 'Content-Type: application/json' -d '" & jsonBody & "' " & fullUrl
    end if
end sentinelCall

on addSentinelRule(ruleText)
    return sentinelCall("/rules", "POST", "{\\"text\\": \\"" & ruleText & "\\"}")
end addSentinelRule

on getSentinelScore()
    return sentinelCall("/stats/score", "GET", "")
end getSentinelScore

on startSentinelFocus(minutes)
    return sentinelCall("/focus/start", "POST", "{\\"duration_minutes\\": " & minutes & "}")
end startSentinelFocus
'''


def run_automator_workflow(workflow_path: str, input_text: str = "") -> str:
    """Run an Automator workflow."""
    try:
        r = subprocess.run(
            ["automator", "-i", input_text, workflow_path],
            capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def activate_app(app_name: str) -> bool:
    """Bring an app to the foreground."""
    script = f'tell application "{app_name}" to activate'
    run_applescript(script)
    return True


def get_running_apps() -> list:
    """Get list of running applications."""
    script = 'tell application "System Events" to get name of every process whose background only is false'
    result = run_applescript(script)
    if result:
        return [a.strip() for a in result.split(",")]
    return []


def quit_app(app_name: str) -> bool:
    script = f'tell application "{app_name}" to quit'
    run_applescript(script)
    return True
