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

// MARK: - AppDelegate

final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var window: NSWindow?
    let daemon = DaemonManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Don't show in dock — menu bar app
        NSApp.setActivationPolicy(.accessory)

        // Status bar item
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.title = "🛡"
            button.target = self
            button.action = #selector(toggleWindow)
        }

        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Dashboard", action: #selector(toggleWindow), keyEquivalent: "o"))
        menu.addItem(NSMenuItem(title: "Reload", action: #selector(reload), keyEquivalent: "r"))
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Quit Sentinel", action: #selector(quit), keyEquivalent: "q"))
        statusItem.menu = menu

        // Start daemon
        daemon.start()

        // Wait briefly then open the window once
        DispatchQueue.global(qos: .userInitiated).async {
            _ = self.daemon.waitForReady(timeout: 8)
            DispatchQueue.main.async { self.openWindow() }
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        daemon.stop()
    }

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
            let webView = WKWebView(frame: w.contentView!.bounds, configuration: config)
            webView.autoresizingMask = [.width, .height]
            webView.setValue(false, forKey: "drawsBackground")
            w.contentView?.addSubview(webView)

            if let url = URL(string: SERVER_URL) {
                webView.load(URLRequest(url: url))
            }
            window = w
        }
        NSApp.activate(ignoringOtherApps: true)
        window?.makeKeyAndOrderFront(nil)
    }

    @objc func reload() {
        if let w = window, let webView = w.contentView?.subviews.compactMap({ $0 as? WKWebView }).first {
            webView.reload()
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
