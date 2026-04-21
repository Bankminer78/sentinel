// LockWidgets.swift — the SwiftUI view rendered in the Dashboard tab.
//
// Two cases:
//   1. Lock has a sibling <name>.html file → render a WKWebView that
//      loads it, with a `window.sentinel` JS bridge injected so the
//      page can read/write the shared SQLite db.
//   2. No sibling html → render a plain SwiftUI fallback showing the
//      lock's running state + last few log events.

import SwiftUI
import WebKit
import AppKit
import SentinelCore

// MARK: - Dispatch

struct DashboardView: View {
    let lock: LockEntry
    @EnvironmentObject var state: AppState
    @EnvironmentObject var processManager: ProcessManager

    var body: some View {
        if let url = lock.dashboardURL {
            DashboardWebView(lock: lock, dashboardURL: url)
        } else {
            StatusWidget(lock: lock)
        }
    }
}

// MARK: - WebView dashboard

/// WKWebView that loads <lock>.html and exposes a `window.sentinel`
/// bridge backed by Database.shared() + ProcessManager. The bridge is
/// injected at document-start so the page can use it in its very first
/// script tag without racing.
struct DashboardWebView: NSViewRepresentable {
    let lock: LockEntry
    let dashboardURL: URL
    @EnvironmentObject var processManager: ProcessManager
    @EnvironmentObject var state: AppState

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true

        // Inject bridge before page scripts run.
        let js = bridgeJS(lockName: lock.name)
        let userScript = WKUserScript(
            source: js,
            injectionTime: .atDocumentStart,
            forMainFrameOnly: true)
        config.userContentController.addUserScript(userScript)

        // Message handler carries the closures we want the bridge to call
        // so we don't have to pass the full AppState/ProcessManager into
        // an NSObject. The closures capture them at view-construction time.
        let handler = SentinelBridgeHandler(
            processManager: processManager,
            lockByName: { [state] name in
                state.locks.first { $0.name == name }
            }
        )
        config.userContentController.add(handler, name: "sentinel")
        context.coordinator.handler = handler

        // Allow dark-mode CSS to work correctly
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground")
        if #available(macOS 13.3, *) {
            webView.isInspectable = true
        }
        handler.webView = webView

        // Allow read access to the whole locks dir so a dashboard can
        // reference e.g. a local CSS or image from the same directory.
        let locksDir = dashboardURL.deletingLastPathComponent()
        webView.loadFileURL(dashboardURL, allowingReadAccessTo: locksDir)
        return webView
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        // If the dashboard file changed on disk (user approved a new
        // version via chat), swap it in.
        if nsView.url != dashboardURL {
            let locksDir = dashboardURL.deletingLastPathComponent()
            nsView.loadFileURL(dashboardURL, allowingReadAccessTo: locksDir)
        }
    }

    final class Coordinator {
        var handler: SentinelBridgeHandler?
    }
}

// MARK: - Bridge

/// Receives `{id, method, args}` messages from the page, dispatches to
/// the right Database / ProcessManager operation, and resolves the JS
/// Promise by calling `window.sentinelResolve(id, value)`.
final class SentinelBridgeHandler: NSObject, WKScriptMessageHandler {
    weak var webView: WKWebView?
    let processManager: ProcessManager
    let lockByName: (String) -> LockEntry?

    init(processManager: ProcessManager,
         lockByName: @escaping (String) -> LockEntry?) {
        self.processManager = processManager
        self.lockByName = lockByName
    }

    func userContentController(_ controller: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any],
              let id = body["id"] as? Int,
              let method = body["method"] as? String else { return }
        let args = (body["args"] as? [Any]) ?? []

        let result = handle(method: method, args: args)

        let wrapped: [String: Any] = ["value": result]
        guard let json = try? JSONSerialization.data(withJSONObject: wrapped,
                                                      options: .fragmentsAllowed),
              let jsonStr = String(data: json, encoding: .utf8) else { return }
        let call = "window.__sentinelResolve(\(id), \(jsonStr).value)"
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(call)
        }
    }

    /// Dispatch table. Keep this small — each new method is one case.
    private func handle(method: String, args: [Any]) -> Any {
        let db = (try? Database.shared())
        switch method {

        // ---- key-value blackboard ----
        case "kv.get":
            guard let key = args.first as? String, let db = db else { return NSNull() }
            let row = try? db.queryFirst("SELECT value FROM kv WHERE key=?", key)
            return row?.string("value") ?? NSNull()

        case "kv.set":
            guard args.count >= 2,
                  let key = args[0] as? String,
                  let db = db else { return false }
            let val = stringify(args[1])
            try? db.execute("""
                INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, key, val, Date().timeIntervalSince1970)
            return true

        case "kv.del":
            guard let key = args.first as? String, let db = db else { return false }
            try? db.execute("DELETE FROM kv WHERE key=?", key)
            return true

        // ---- running table ----
        case "running":
            guard let name = args.first as? String, let db = db else { return NSNull() }
            guard let row = (try? db.queryFirst(
                "SELECT * FROM running WHERE name=?", name)) ?? nil
            else { return NSNull() }
            return [
                "pid": row.int("pid") ?? 0,
                "startedAt": row.double("started_at") ?? 0,
                "lastHeartbeat": row.double("last_heartbeat") ?? 0,
                "statusText": row.string("status_text") ?? NSNull(),
            ] as [String: Any]

        // ---- audit log ----
        case "logs":
            guard let name = args.first as? String, let db = db else { return [] as [Any] }
            let limit = (args.count > 1 ? (args[1] as? Int) : nil) ?? 50
            let rows = (try? db.query(
                "SELECT * FROM log WHERE source=? ORDER BY ts DESC LIMIT ?",
                name, limit)) ?? []
            return rows.map { row -> [String: Any] in
                [
                    "id":      row.int("id") ?? 0,
                    "ts":      row.double("ts") ?? 0,
                    "source":  row.string("source") ?? "",
                    "event":   row.string("event") ?? "",
                    "payload": row.string("payload") ?? NSNull(),
                ]
            }

        // ---- process control ----
        case "run":
            guard let name = args.first as? String,
                  let lock = lockByName(name) else { return false }
            DispatchQueue.main.async {
                self.processManager.run(lock: lock)
            }
            return true

        case "stop":
            guard let name = args.first as? String else { return false }
            DispatchQueue.main.async {
                self.processManager.stop(name: name)
            }
            return true

        // ---- commitments ----
        case "commit":
            guard args.count >= 3,
                  let kind = args[0] as? String,
                  let secs = (args[2] as? Int) ?? (args[2] as? Double).map(Int.init),
                  let db = db else { return false }
            let target = (args[1] as? String).flatMap { $0.isEmpty ? nil : $0 }
            let now = Date().timeIntervalSince1970
            try? db.execute("""
                INSERT INTO commitments (kind, target, until_ts, friction, created_at)
                VALUES (?, ?, ?, NULL, ?)
            """, kind, target as Any, now + Double(secs), now)
            return true

        case "committed":
            guard let kind = args.first as? String, let db = db else { return false }
            let target = args.count > 1 ? (args[1] as? String) : nil
            let now = Date().timeIntervalSince1970
            let row: Row?
            if let target = target {
                row = try? db.queryFirst("""
                    SELECT id FROM commitments
                     WHERE kind=? AND released_at IS NULL AND until_ts > ?
                       AND (target=? OR target IS NULL) LIMIT 1
                """, kind, now, target)
            } else {
                row = try? db.queryFirst("""
                    SELECT id FROM commitments
                     WHERE kind=? AND released_at IS NULL AND until_ts > ? LIMIT 1
                """, kind, now)
            }
            return row != nil

        // ---- world state ----
        case "world":
            guard let db = db else { return NSNull() }
            guard let row = (try? db.queryFirst(
                "SELECT * FROM world ORDER BY ts DESC LIMIT 1")) ?? nil
            else { return NSNull() }
            let windowsJSON = row.string("windows") ?? "[]"
            let windows: Any = (try? JSONSerialization.jsonObject(
                with: Data(windowsJSON.utf8))) ?? []
            return [
                "ts": row.double("ts") ?? 0,
                "windows": windows,
                "foregroundApp": row.string("foreground_app") ?? NSNull(),
                "foregroundWindow": row.string("foreground_window") ?? NSNull(),
            ] as [String: Any]

        default:
            return NSNull()
        }
    }

    private func stringify(_ v: Any) -> String {
        switch v {
        case let s as String: return s
        case let i as Int: return String(i)
        case let d as Double: return String(d)
        case let b as Bool: return b ? "true" : "false"
        default:
            if let data = try? JSONSerialization.data(
                withJSONObject: v, options: .fragmentsAllowed),
               let s = String(data: data, encoding: .utf8) {
                return s
            }
            return "\(v)"
        }
    }
}

/// JS injected at document-start. Shapes the `window.sentinel` API the
/// dashboards use. Every call returns a Promise that the Swift side
/// resolves via `window.__sentinelResolve(id, value)`.
private func bridgeJS(lockName: String) -> String {
    return """
    (() => {
      const pending = {};
      let nextId = 0;
      function call(method, args) {
        return new Promise((resolve) => {
          const id = ++nextId;
          pending[id] = resolve;
          window.webkit.messageHandlers.sentinel.postMessage({id, method, args});
        });
      }
      window.__sentinelResolve = (id, value) => {
        const r = pending[id];
        if (r) { delete pending[id]; r(value); }
      };
      window.sentinel = {
        lockName: \(jsString(lockName)),
        kv: {
          get: (k) => call("kv.get", [k]),
          set: (k, v) => call("kv.set", [k, v]),
          del: (k) => call("kv.del", [k]),
        },
        running: (n) => call("running", [n || \(jsString(lockName))]),
        logs: (n, limit) => call("logs", [n || \(jsString(lockName)), limit || 50]),
        run: (n) => call("run", [n || \(jsString(lockName))]),
        stop: (n) => call("stop", [n || \(jsString(lockName))]),
        commit: (kind, target, secs) => call("commit", [kind, target, secs]),
        committed: (kind, target) => call("committed", [kind, target || null]),
        world: () => call("world", []),
      };
    })();
    """
}

private func jsString(_ s: String) -> String {
    // Minimal JS-string escaping — the only characters we ever pass are
    // lock names which are basenames of files, but be defensive.
    let esc = s
        .replacingOccurrences(of: "\\", with: "\\\\")
        .replacingOccurrences(of: "\"", with: "\\\"")
        .replacingOccurrences(of: "\n", with: "\\n")
    return "\"\(esc)\""
}

// MARK: - Status widget (fallback for locks without <name>.html)

struct StatusWidget: View {
    let lock: LockEntry
    @EnvironmentObject var state: AppState
    @State private var lastLogs: [LogRow] = []
    @State private var timer: Timer?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer()
            card.frame(maxWidth: .infinity).padding(.horizontal, 40)
            Spacer()
            logsView.padding(.horizontal, 40).padding(.bottom, 24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { start() }
        .onDisappear { stop() }
    }

    private var card: some View {
        VStack(spacing: 12) {
            if let info = state.runningByName[lock.name] {
                Label("running", systemImage: "circle.fill")
                    .labelStyle(.titleAndIcon)
                    .font(.caption)
                    .foregroundStyle(.green)
                    .textCase(.uppercase)
                Text(info.statusText ?? "…")
                    .font(.system(size: 42, weight: .light, design: .rounded))
                    .monospacedDigit()
                    .multilineTextAlignment(.center)
                Text("pid \(info.pid) · started \(fmtRelative(info.startedAt))")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            } else {
                Label("idle", systemImage: "circle")
                    .labelStyle(.titleAndIcon)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                Text("Not engaged")
                    .font(.system(size: 34, weight: .light, design: .rounded))
                    .foregroundStyle(.secondary)
                Text("click Run to start")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            Text("Write a `\(lock.name).html` next to the script for a custom dashboard.")
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .padding(.top, 8)
        }
        .padding(24)
        .background(Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var logsView: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("recent activity")
                .font(.caption)
                .textCase(.uppercase)
                .foregroundStyle(.tertiary)
                .tracking(1)
            if lastLogs.isEmpty {
                Text("no events yet")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .italic()
            } else {
                ForEach(lastLogs) { row in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(fmtTime(row.ts))
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundStyle(.tertiary)
                            .frame(width: 60, alignment: .leading)
                        Text(row.event)
                            .font(.caption)
                            .frame(width: 120, alignment: .leading)
                        Text(row.payload ?? "")
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func start() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in refresh() }
    }
    private func stop() { timer?.invalidate(); timer = nil }

    private func refresh() {
        guard let db = try? Database.shared() else { return }
        let rows = (try? db.query(
            "SELECT * FROM log WHERE source=? ORDER BY ts DESC LIMIT 10",
            lock.name)) ?? []
        let logs = rows.compactMap { LogRow($0) }
        if logs.map(\.id) != lastLogs.map(\.id) {
            lastLogs = logs
        }
    }

    private func fmtTime(_ ts: Double) -> String {
        let f = DateFormatter(); f.dateFormat = "HH:mm:ss"
        return f.string(from: Date(timeIntervalSince1970: ts))
    }

    private func fmtRelative(_ ts: Double) -> String {
        let d = Date().timeIntervalSince1970 - ts
        if d < 60 { return "\(Int(d))s ago" }
        if d < 3600 { return "\(Int(d / 60))m ago" }
        return "\(Int(d / 3600))h ago"
    }
}
