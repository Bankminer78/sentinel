// Controls.swift — small wrappers around the few CLI verbs the GUI
// triggers directly. We don't shell out to the CLI binary because both
// the GUI and the CLI open the same SQLite db; calling the CLI would
// just spawn a subprocess to do an INSERT we can do here in 5 lines.
//
// These are "user actions" — they correspond 1:1 to buttons in the
// sidebar (pause, resume, emergency exit, stop-all-running).

import Foundation
import SentinelCore

enum Controls {
    /// True if the global pause flag is set in kv.
    static func isPaused() -> Bool {
        guard let db = try? Database.shared(),
              let row = try? db.queryFirst("SELECT value FROM kv WHERE key=?",
                                           SentinelCore.pausedKey),
              let v = row.string("value") else { return false }
        return v == "true" || v == "1"
    }

    /// `sentinel pause` equivalent. Sets kv['paused'] = "true".
    static func pause() {
        guard let db = try? Database.shared() else { return }
        try? db.execute("""
            INSERT INTO kv (key, value, updated_at) VALUES (?, 'true', ?)
            ON CONFLICT(key) DO UPDATE SET value='true', updated_at=excluded.updated_at
        """, SentinelCore.pausedKey, Date().timeIntervalSince1970)
        try? db.execute(
            "INSERT INTO log (ts, source, event, payload) VALUES (?, 'app', 'pause', NULL)",
            Date().timeIntervalSince1970)
    }

    /// `sentinel resume` equivalent.
    static func resume() {
        guard let db = try? Database.shared() else { return }
        try? db.execute("DELETE FROM kv WHERE key=?", SentinelCore.pausedKey)
        try? db.execute(
            "INSERT INTO log (ts, source, event, payload) VALUES (?, 'app', 'resume', NULL)",
            Date().timeIntervalSince1970)
    }

    /// `sentinel emergency-exit <reason>` equivalent. Releases every
    /// active commitment, sets the global pause flag, and writes the
    /// emergency_exits row. Returns the count released.
    @discardableResult
    static func emergencyExit(reason: String) -> Int {
        guard let db = try? Database.shared() else { return 0 }
        let now = Date().timeIntervalSince1970
        let active = (try? db.query(
            "SELECT id FROM commitments WHERE released_at IS NULL AND until_ts > ?",
            now)) ?? []
        let count = active.count
        try? db.execute(
            "UPDATE commitments SET released_at=? WHERE released_at IS NULL AND until_ts > ?",
            now, now)
        try? db.execute("""
            INSERT INTO kv (key, value, updated_at) VALUES (?, 'true', ?)
            ON CONFLICT(key) DO UPDATE SET value='true', updated_at=excluded.updated_at
        """, SentinelCore.pausedKey, now)
        let payload = "{\"reason\":\"\(reason.replacingOccurrences(of: "\"", with: "\\\""))\"," +
                      "\"released_count\":\(count)}"
        try? db.execute(
            "INSERT INTO log (ts, source, event, payload) VALUES (?, 'user', 'emergency_exit', ?)",
            now, payload)
        try? db.execute(
            "INSERT INTO emergency_exits (ts, reason, released_count) VALUES (?, ?, ?)",
            now, reason, count)
        return count
    }

    /// Recent rows from the audit log, newest first.
    static func recentLog(limit: Int = 200) -> [LogRow] {
        guard let db = try? Database.shared(),
              let rows = try? db.query(
                "SELECT * FROM log ORDER BY ts DESC LIMIT ?", limit) else { return [] }
        return rows.compactMap { LogRow($0) }
    }
}
