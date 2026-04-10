// Sentinel macOS app — menu bar + WKWebView wrapping the local FastAPI server.
// Manages the Python daemon lifecycle and shows the UI in a native window.
import Cocoa
import WebKit

let SERVER_PORT = 9849
let SERVER_URL = "http://127.0.0.1:\(SERVER_PORT)"

// MARK: - DaemonManager

func debugLog(_ msg: String) {
    let logPath = "\(NSHomeDirectory())/Library/Logs/SentinelDebug.log"
    let line = "\(Date()) \(msg)\n"
    if let data = line.data(using: .utf8) {
        if FileManager.default.fileExists(atPath: logPath) {
            if let h = FileHandle(forWritingAtPath: logPath) {
                h.seekToEndOfFile()
                h.write(data)
                h.closeFile()
            }
        } else {
            try? data.write(to: URL(fileURLWithPath: logPath))
        }
    }
}

final class DaemonManager {
    private var process: Process?

    func start() {
        debugLog("DaemonManager.start() called")
        if isRunning() { debugLog("Already running"); return }
        let proc = Process()

        let pythonPaths = [
            "\(NSHomeDirectory())/git/sentinel/.venv/bin/python",
            "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3",
            "/usr/local/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/bin/python3",
        ]
        let python = pythonPaths.first(where: { FileManager.default.fileExists(atPath: $0) }) ?? "/usr/bin/python3"
        let workDir = "\(NSHomeDirectory())/git/sentinel"

        proc.executableURL = URL(fileURLWithPath: python)
        proc.arguments = ["-m", "sentinel.cli", "serve", "--port", "\(SERVER_PORT)"]
        proc.currentDirectoryURL = URL(fileURLWithPath: workDir)

        // Log to a file we can inspect
        let logPath = "\(NSHomeDirectory())/Library/Logs/Sentinel.log"
        FileManager.default.createFile(atPath: logPath, contents: nil)
        if let handle = FileHandle(forWritingAtPath: logPath) {
            proc.standardOutput = handle
            proc.standardError = handle
        }

        // PYTHONPATH so the module can be imported
        var env = ProcessInfo.processInfo.environment
        env["PYTHONPATH"] = workDir
        proc.environment = env

        debugLog("Python: \(python) (exists=\(FileManager.default.fileExists(atPath: python)))")
        debugLog("WorkDir: \(workDir) (exists=\(FileManager.default.fileExists(atPath: workDir)))")
        do {
            try proc.run()
            self.process = proc
            debugLog("Daemon started, pid=\(proc.processIdentifier)")
        } catch {
            debugLog("Failed to start daemon: \(error)")
        }
    }

    func stop() {
        process?.terminate()
        process = nil
    }

    func isRunning() -> Bool {
        guard let p = process else { return false }
        return p.isRunning
    }

    func waitForReady(timeout: TimeInterval = 10) -> Bool {
        let deadline = Date().addingTimeInterval(timeout)
        while Date() < deadline {
            if let url = URL(string: "\(SERVER_URL)/health") {
                let req = URLRequest(url: url, timeoutInterval: 1)
                let sema = DispatchSemaphore(value: 0)
                var ready = false
                URLSession.shared.dataTask(with: req) { data, response, _ in
                    if let r = response as? HTTPURLResponse, r.statusCode == 200 { ready = true }
                    sema.signal()
                }.resume()
                _ = sema.wait(timeout: .now() + 2)
                if ready { return true }
            }
            Thread.sleep(forTimeInterval: 0.3)
        }
        return false
    }
}

// MARK: - LockoutManager (Frozen Turkey)

/// Polls /screen-lock/state every second. When active, takes over every
/// connected screen with a borderless full-screen window that the user
/// cannot dismiss. The only way out is the emergency-exit endpoint, which
/// the lockout window deliberately doesn't expose.
final class LockoutManager {
    private var windows: [NSWindow] = []
    private var labels: [NSTextField] = []
    private var timer: Timer?
    private var pollTimer: Timer?
    private var endTime: Date?
    private var message: String = ""

    func start() {
        // Poll the daemon every second for state
        pollTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.poll()
        }
    }

    private func poll() {
        guard let url = URL(string: "\(SERVER_URL)/screen-lock/state") else { return }
        let req = URLRequest(url: url, timeoutInterval: 1)
        URLSession.shared.dataTask(with: req) { [weak self] data, _, _ in
            guard let self = self,
                  let data = data,
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
            else { return }
            let active = obj["active"] as? Bool ?? false
            let untilTs = obj["until_ts"] as? Double
            let msg = (obj["message"] as? String) ?? "Focus mode"
            DispatchQueue.main.async {
                if active, let ts = untilTs {
                    self.showLockout(until: Date(timeIntervalSince1970: ts), message: msg)
                } else {
                    self.hideLockout()
                }
            }
        }.resume()
    }

    private func showLockout(until: Date, message: String) {
        // Already showing? Just update the end time / message.
        if !windows.isEmpty {
            self.endTime = until
            self.message = message
            return
        }
        debugLog("LockoutManager.showLockout until=\(until) msg=\(message)")
        self.endTime = until
        self.message = message
        for screen in NSScreen.screens {
            let w = NSWindow(
                contentRect: screen.frame,
                styleMask: [.borderless],
                backing: .buffered, defer: false
            )
            w.level = .screenSaver
            w.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
            w.backgroundColor = NSColor.black.withAlphaComponent(0.97)
            w.isOpaque = false
            w.ignoresMouseEvents = false
            w.hasShadow = false

            let titleLabel = NSTextField(labelWithString: message)
            titleLabel.font = NSFont.systemFont(ofSize: 56, weight: .bold)
            titleLabel.textColor = .white
            titleLabel.alignment = .center
            titleLabel.backgroundColor = .clear
            titleLabel.isBordered = false
            titleLabel.frame = NSRect(
                x: 0, y: screen.frame.height / 2,
                width: screen.frame.width, height: 80
            )
            titleLabel.autoresizingMask = [.minXMargin, .maxXMargin, .minYMargin, .maxYMargin]

            let timerLabel = NSTextField(labelWithString: "")
            timerLabel.font = NSFont.monospacedDigitSystemFont(ofSize: 96, weight: .light)
            timerLabel.textColor = .white
            timerLabel.alignment = .center
            timerLabel.backgroundColor = .clear
            timerLabel.isBordered = false
            timerLabel.frame = NSRect(
                x: 0, y: screen.frame.height / 2 - 140,
                width: screen.frame.width, height: 110
            )
            timerLabel.autoresizingMask = [.minXMargin, .maxXMargin, .minYMargin, .maxYMargin]

            let hint = NSTextField(labelWithString: "Frozen until the timer ends. Use emergency exit if this is real.")
            hint.font = NSFont.systemFont(ofSize: 14)
            hint.textColor = NSColor.white.withAlphaComponent(0.4)
            hint.alignment = .center
            hint.backgroundColor = .clear
            hint.isBordered = false
            hint.frame = NSRect(
                x: 0, y: screen.frame.height / 2 - 200,
                width: screen.frame.width, height: 30
            )
            hint.autoresizingMask = [.minXMargin, .maxXMargin, .minYMargin, .maxYMargin]

            w.contentView?.addSubview(titleLabel)
            w.contentView?.addSubview(timerLabel)
            w.contentView?.addSubview(hint)
            w.makeKeyAndOrderFront(nil)

            windows.append(w)
            labels.append(timerLabel)
        }
        // Drive the countdown labels at 1Hz
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            self?.tick()
        }
        tick()
        NSApp.activate(ignoringOtherApps: true)
    }

    private func tick() {
        guard let end = endTime else { return }
        let remaining = max(0, end.timeIntervalSinceNow)
        let mins = Int(remaining) / 60
        let secs = Int(remaining) % 60
        let text = String(format: "%02d:%02d", mins, secs)
        for label in labels {
            label.stringValue = text
        }
        if remaining <= 0 {
            hideLockout()
        }
    }

    private func hideLockout() {
        if windows.isEmpty { return }
        debugLog("LockoutManager.hideLockout")
        timer?.invalidate()
        timer = nil
        for w in windows {
            w.orderOut(nil)
        }
        windows.removeAll()
        labels.removeAll()
        endTime = nil
    }
}


// MARK: - AppDelegate

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate {
    var statusItem: NSStatusItem!
    var window: NSWindow?
    var webView: WKWebView?
    let daemon = DaemonManager()
    let lockout = LockoutManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Don't show in dock — menu bar app
        NSApp.setActivationPolicy(.accessory)

        // Status bar item — left-click opens the dashboard, right-click shows
        // the menu. This avoids forcing the user through Open Dashboard every
        // time they want the window.
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.title = "🛡"
            button.target = self
            button.action = #selector(statusBarClick)
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }

        // Start daemon
        daemon.start()

        // Wait briefly then open the window once
        DispatchQueue.global(qos: .userInitiated).async {
            _ = self.daemon.waitForReady(timeout: 8)
            DispatchQueue.main.async {
                self.openWindow()
                self.lockout.start()
            }
        }
    }

    /// Re-opens the dashboard when the user clicks Sentinel.app while it's
    /// already running. Without this, double-clicking the .app does nothing
    /// visible because the existing instance just refocuses with no window.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            openWindow()
        }
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        daemon.stop()
    }

    /// Left-click → toggle dashboard. Right-click (or control-click) → menu.
    @objc func statusBarClick() {
        guard let event = NSApp.currentEvent else {
            toggleWindow()
            return
        }
        if event.type == .rightMouseUp || event.modifierFlags.contains(.control) {
            // Show the menu by attaching it temporarily
            let menu = NSMenu()
            menu.addItem(NSMenuItem(title: "Open Dashboard", action: #selector(openWindowAction), keyEquivalent: "o"))
            menu.addItem(NSMenuItem(title: "Reload", action: #selector(reload), keyEquivalent: "r"))
            menu.addItem(.separator())
            menu.addItem(NSMenuItem(title: "Quit Sentinel", action: #selector(quit), keyEquivalent: "q"))
            statusItem.menu = menu
            statusItem.button?.performClick(nil)
            // Detach so the next left-click runs the action again
            statusItem.menu = nil
        } else {
            toggleWindow()
        }
    }

    @objc func openWindowAction() { openWindow() }

    @objc func toggleWindow() {
        if let w = window, w.isVisible {
            w.orderOut(nil)
        } else {
            openWindow()
        }
    }

    func openWindow() {
        if window == nil {
            let w = NSWindow(
                contentRect: NSRect(x: 0, y: 0, width: 980, height: 640),
                styleMask: [.titled, .closable, .resizable, .fullSizeContentView],
                backing: .buffered, defer: false
            )
            w.title = "Sentinel"
            w.titlebarAppearsTransparent = true
            w.titleVisibility = .hidden
            w.center()
            w.isReleasedWhenClosed = false

            let config = WKWebViewConfiguration()
            let wv = WKWebView(frame: w.contentView!.bounds, configuration: config)
            wv.autoresizingMask = [.width, .height]
            wv.setValue(false, forKey: "drawsBackground")
            wv.navigationDelegate = self
            w.contentView?.addSubview(wv)

            if let url = URL(string: SERVER_URL) {
                wv.load(URLRequest(url: url))
            }
            self.webView = wv
            window = w
        } else if let wv = self.webView {
            // Window exists. If the page is in an error state (e.g., the
            // daemon was killed and the WKWebView is showing
            // ERR_CONNECTION_REFUSED), reload it.
            if wv.url == nil || wv.url?.absoluteString == "about:blank" {
                if let url = URL(string: SERVER_URL) {
                    wv.load(URLRequest(url: url))
                }
            }
        }
        NSApp.activate(ignoringOtherApps: true)
        window?.makeKeyAndOrderFront(nil)
    }

    // MARK: - WKNavigationDelegate (auto-recover from page-load failures)

    func webView(_ wv: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        debugLog("webView didFailProvisionalNavigation: \(error.localizedDescription)")
        // The most common cause is the daemon not yet ready. Retry once after
        // a short delay so the user doesn't see a blank/error page.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            guard let self = self, let url = URL(string: SERVER_URL) else { return }
            wv.load(URLRequest(url: url))
        }
    }

    func webView(_ wv: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        debugLog("webView didFail: \(error.localizedDescription)")
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            guard let self = self, let url = URL(string: SERVER_URL) else { return }
            wv.load(URLRequest(url: url))
        }
    }

    @objc func reload() {
        // Force a fresh fetch of the daemon's HTML, not just a cached reload
        if let wv = self.webView, let url = URL(string: SERVER_URL) {
            wv.load(URLRequest(url: url))
        }
    }

    @objc func quit() {
        daemon.stop()
        NSApp.terminate(nil)
    }
}

// MARK: - Entry point

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
