// WorldRecorder.swift — continuous CGWindowList logger.
//
// Runs as long as SentinelApp is alive. Every `intervalS` seconds,
// captures the visible window list, the foreground app, and the
// focused window's title, and appends a row to the `world` table.
// Locks (and the user via `sentinel world`) can read this snapshot to
// understand what was happening at any moment in the recent past.
//
// Cost discipline: ~5ms per tick on average. The osascript call for
// the focused window title is the only thing that can hang, so it's
// wrapped with a hard 1s timeout.

import Foundation
import AppKit
import CoreGraphics
import SentinelCore

public final class WorldRecorder {
    private let db: Database
    private let intervalS: TimeInterval
    private var task: Task<Void, Never>?
    private var lastPruneAt: Double = 0

    public init(db: Database, intervalS: TimeInterval = 2.0) {
        self.db = db
        self.intervalS = intervalS
    }

    public func start() {
        guard task == nil else { return }
        task = Task.detached(priority: .background) { [weak self] in
            await self?.run()
        }
    }

    public func stop() {
        task?.cancel()
        task = nil
    }

    private func run() async {
        while !Task.isCancelled {
            do {
                try tickOnce()
            } catch {
                fputs("WorldRecorder tick failed: \(error)\n", stderr)
            }
            try? await Task.sleep(nanoseconds: UInt64(intervalS * 1_000_000_000))
        }
    }

    /// Capture one snapshot and write it. Public so tests / standalone
    /// runners can call it directly without spinning the loop.
    public func tickOnce() throws {
        let now = Date().timeIntervalSince1970
        let windows = captureWindows()
        let app = NSWorkspace.shared.frontmostApplication?.localizedName ?? ""
        let title = focusedWindowTitle(forApp: app)

        let json = (try? JSONSerialization.data(withJSONObject: windows)) ?? Data("[]".utf8)
        let jsonStr = String(data: json, encoding: .utf8) ?? "[]"

        try db.execute("""
            INSERT INTO world (ts, windows, foreground_app, foreground_window)
            VALUES (?, ?, ?, ?)
        """, now, jsonStr, app, title)

        // Prune older than 7 days, at most once per hour.
        if now - lastPruneAt > 3600 {
            lastPruneAt = now
            let cutoff = now - 7 * 86400
            try db.execute("DELETE FROM world WHERE ts < ?", cutoff)
        }
    }

    // MARK: - Sensors

    private func captureWindows() -> [[String: Any]] {
        let opts: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
        guard let infos = CGWindowListCopyWindowInfo(opts, kCGNullWindowID) as? [[String: Any]] else {
            return []
        }
        var out: [[String: Any]] = []
        for info in infos {
            let layer = info[kCGWindowLayer as String] as? Int ?? 0
            // Skip menu bars / dock / overlays — only application windows.
            if layer != 0 { continue }
            let app = info[kCGWindowOwnerName as String] as? String ?? ""
            let title = info[kCGWindowName as String] as? String ?? ""
            let pid = info[kCGWindowOwnerPID as String] as? Int ?? 0
            let bounds = info[kCGWindowBounds as String] as? [String: CGFloat] ?? [:]
            out.append([
                "app": app,
                "title": title,
                "pid": pid,
                "layer": layer,
                "bounds": [
                    "x": Double(bounds["X"] ?? 0),
                    "y": Double(bounds["Y"] ?? 0),
                    "w": Double(bounds["Width"] ?? 0),
                    "h": Double(bounds["Height"] ?? 0),
                ] as [String: Any],
            ])
        }
        return out
    }

    /// Best-effort focused window title via System Events. Some apps
    /// don't expose AX info; in those cases osascript errors and we
    /// return empty. Hard 1s timeout because System Events can hang
    /// on misbehaving apps.
    private func focusedWindowTitle(forApp app: String) -> String {
        guard !app.isEmpty else { return "" }
        let escaped = app.replacingOccurrences(of: "\"", with: "\\\"")
        let script = """
        tell application "System Events"
            try
                tell process "\(escaped)" to get name of front window
            on error
                return ""
            end try
        end tell
        """
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        proc.arguments = ["-e", script]
        let outPipe = Pipe()
        let errPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = errPipe
        do {
            try proc.run()
        } catch {
            return ""
        }
        let deadline = Date().addingTimeInterval(1.0)
        while proc.isRunning && Date() < deadline {
            Thread.sleep(forTimeInterval: 0.02)
        }
        if proc.isRunning {
            proc.terminate()
            return ""
        }
        let data = outPipe.fileHandleForReading.availableData
        return String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }
}
