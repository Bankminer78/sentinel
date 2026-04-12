// sentinel CLI — the cross-lock primitives every script can shell out to.
//
// Usage:
//   sentinel check <name>            heartbeat + pause/stop check
//   sentinel log <source> <event> [json]
//   sentinel status <name> <text>
//   sentinel commit <kind> <target> <secs> [--friction TYPE:N]
//   sentinel committed <kind> [target]
//   sentinel kv get <key>
//   sentinel kv set <key> <value>
//   sentinel kv del <key>
//   sentinel pause
//   sentinel resume
//   sentinel emergency-exit <reason>
//   sentinel world
//   sentinel running
//   sentinel help
//
// Exit codes:
//   0  — success / "yes"
//   1  — "no" (used by `check` when paused/stopped, by `committed` when not locked)
//   2  — usage error
//   3  — internal/database error

import Foundation
import SentinelCore

// MARK: - Top-level dispatch

let argv = CommandLine.arguments
guard argv.count >= 2 else {
    printUsage()
    exit(2)
}

let verb = argv[1]
let rest = Array(argv.dropFirst(2))

do {
    let db = try Database.shared()
    switch verb {
    case "check":          try cmdCheck(db, rest)
    case "log":            try cmdLog(db, rest)
    case "status":         try cmdStatus(db, rest)
    case "commit":         try cmdCommit(db, rest)
    case "committed":      try cmdCommitted(db, rest)
    case "kv":             try cmdKV(db, rest)
    case "pause":          try cmdPause(db)
    case "resume":         try cmdResume(db)
    case "emergency-exit": try cmdEmergencyExit(db, rest)
    case "world":          try cmdWorld(db)
    case "running":        try cmdRunning(db)
    case "help", "--help", "-h":
        printUsage()
        exit(0)
    default:
        FileHandle.standardError.write("unknown verb: \(verb)\n".data(using: .utf8)!)
        printUsage()
        exit(2)
    }
} catch {
    FileHandle.standardError.write("error: \(error)\n".data(using: .utf8)!)
    exit(3)
}

// MARK: - Helpers

func now() -> Double { Date().timeIntervalSince1970 }

func usageError(_ msg: String) -> Never {
    FileHandle.standardError.write("usage error: \(msg)\n".data(using: .utf8)!)
    exit(2)
}

func printJSON(_ obj: Any) {
    let data = try? JSONSerialization.data(
        withJSONObject: obj,
        options: [.prettyPrinted, .sortedKeys])
    if let data = data, let str = String(data: data, encoding: .utf8) {
        print(str)
    }
}

func rowToJSONValue(_ row: Row) -> [String: Any] {
    var out: [String: Any] = [:]
    for (k, v) in row.columns {
        switch v {
        case let i as Int64: out[k] = i
        case let d as Double: out[k] = d
        case let s as String: out[k] = s
        default: out[k] = "\(v)"
        }
    }
    return out
}

func printUsage() {
    let usage = """
    sentinel — cross-lock primitives over a shared SQLite db

    USAGE:
      sentinel <verb> [args...]

    VERBS:
      check <name>                    Heartbeat for <name> + global pause + per-lock stop
                                      check. Exits 1 if the script should bail.
      log <source> <event> [json]     Append a row to the audit log.
      status <name> <text>            Set the sidebar status string for a running lock.
      commit <kind> <target> <secs>   Create a write-once commitment.
        [--friction TYPE:N]            wait:N | type_text:N
      committed <kind> [target]       Exits 0 if a matching commitment is active, 1 otherwise.
      kv get <key>                    Read from the cross-lock blackboard.
      kv set <key> <value>            Write.
      kv del <key>                    Delete.
      pause                           Set the global pause flag.
      resume                          Clear it.
      emergency-exit <reason>         Release all commitments + pause + log + decrement budget.
      world                           Print the latest world snapshot as JSON.
      running                         Print the running table as JSON.
      help                            Show this message.

    All verbs operate on ~/Library/Application Support/Sentinel/sentinel.db.
    """
    print(usage)
}

// MARK: - Verbs

/// `sentinel check <name>` — heartbeat + pause/stop check.
///
/// Updates the running row's last_heartbeat (and inserts the row on
/// first call). Exits 1 (and removes the running row) if either the
/// global pause flag or the per-lock stop flag is set.
func cmdCheck(_ db: Database, _ args: [String]) throws {
    guard let name = args.first else { usageError("check <name>") }
    let pid = ProcessInfo.processInfo.processIdentifier
    let t = now()

    // Check pause + per-lock stop FIRST so a freshly-paused lock can't
    // sneak in another tick by writing its heartbeat.
    if try isPaused(db) || isStopped(db, name: name) {
        try db.execute("DELETE FROM running WHERE name=?", name)
        exit(1)
    }

    // Upsert the heartbeat. SQLite supports ON CONFLICT.
    try db.execute("""
        INSERT INTO running (name, pid, started_at, last_heartbeat, status_text)
        VALUES (?, ?, ?, ?, NULL)
        ON CONFLICT(name) DO UPDATE SET
            pid = excluded.pid,
            last_heartbeat = excluded.last_heartbeat
    """, name, Int(pid), t, t)
    exit(0)
}

func isPaused(_ db: Database) throws -> Bool {
    if let row = try db.queryFirst("SELECT value FROM kv WHERE key=?", SentinelCore.pausedKey),
       let v = row.string("value") {
        return v == "true" || v == "1"
    }
    return false
}

func isStopped(_ db: Database, name: String) throws -> Bool {
    if let row = try db.queryFirst("SELECT value FROM kv WHERE key=?", SentinelCore.stopKey(name)),
       let v = row.string("value") {
        return v == "true" || v == "1"
    }
    return false
}

/// `sentinel log <source> <event> [json]`
func cmdLog(_ db: Database, _ args: [String]) throws {
    guard args.count >= 2 else { usageError("log <source> <event> [json]") }
    let source = args[0]
    let event = args[1]
    let payload: Any? = args.count >= 3 ? args[2] : nil
    try db.execute(
        "INSERT INTO log (ts, source, event, payload) VALUES (?, ?, ?, ?)",
        now(), source, event, payload)
    exit(0)
}

/// `sentinel status <name> <text>`
func cmdStatus(_ db: Database, _ args: [String]) throws {
    guard args.count >= 2 else { usageError("status <name> <text>") }
    let name = args[0]
    let text = args[1]
    // Only update if the row exists; the lock should call check first.
    try db.execute(
        "UPDATE running SET status_text=? WHERE name=?",
        text, name)
    exit(0)
}

/// `sentinel commit <kind> <target> <secs> [--friction TYPE:N]`
func cmdCommit(_ db: Database, _ args: [String]) throws {
    guard args.count >= 3 else {
        usageError("commit <kind> <target> <secs> [--friction TYPE:N]")
    }
    let kind = args[0]
    let target = args[1].isEmpty || args[1] == "-" ? nil : args[1]
    guard let secs = Double(args[2]), secs > 0 else {
        usageError("secs must be a positive number")
    }

    var friction: String? = nil
    if let i = args.firstIndex(of: "--friction"), i + 1 < args.count {
        // Validate "TYPE:N"
        let raw = args[i + 1]
        let parts = raw.split(separator: ":")
        guard parts.count == 2,
              let n = Int(parts[1]),
              ["wait", "type_text"].contains(String(parts[0])) else {
            usageError("--friction TYPE:N where TYPE is wait|type_text and N is an int")
        }
        friction = "{\"type\":\"\(parts[0])\",\"n\":\(n)}"
    }

    let createdAt = now()
    let until = createdAt + secs
    try db.execute("""
        INSERT INTO commitments (kind, target, until_ts, friction, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, kind, target as Any, until, friction as Any, createdAt)

    let id = db.lastInsertRowID()
    print(id)
    exit(0)
}

/// `sentinel committed <kind> [target]` — exit 0 if active commitment exists.
func cmdCommitted(_ db: Database, _ args: [String]) throws {
    guard let kind = args.first else { usageError("committed <kind> [target]") }
    let target: String? = args.count >= 2 ? args[1] : nil
    let t = now()

    let row: Row?
    if let target = target {
        row = try db.queryFirst("""
            SELECT id FROM commitments
             WHERE kind = ? AND released_at IS NULL AND until_ts > ?
               AND (target = ? OR target IS NULL)
             LIMIT 1
        """, kind, t, target)
    } else {
        row = try db.queryFirst("""
            SELECT id FROM commitments
             WHERE kind = ? AND released_at IS NULL AND until_ts > ?
             LIMIT 1
        """, kind, t)
    }
    exit(row == nil ? 1 : 0)
}

/// `sentinel kv get|set|del <key> [value]`
func cmdKV(_ db: Database, _ args: [String]) throws {
    guard args.count >= 2 else { usageError("kv get|set|del <key> [value]") }
    let sub = args[0]
    let key = args[1]
    switch sub {
    case "get":
        if let row = try db.queryFirst("SELECT value FROM kv WHERE key=?", key),
           let v = row.string("value") {
            print(v)
            exit(0)
        }
        exit(1)
    case "set":
        guard args.count >= 3 else { usageError("kv set <key> <value>") }
        try db.execute("""
            INSERT INTO kv (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
        """, key, args[2], now())
        exit(0)
    case "del":
        try db.execute("DELETE FROM kv WHERE key=?", key)
        exit(0)
    default:
        usageError("kv subcommand must be get|set|del")
    }
}

/// `sentinel pause` — set the global pause flag.
func cmdPause(_ db: Database) throws {
    try db.execute("""
        INSERT INTO kv (key, value, updated_at) VALUES (?, 'true', ?)
        ON CONFLICT(key) DO UPDATE SET value='true', updated_at=excluded.updated_at
    """, SentinelCore.pausedKey, now())
    exit(0)
}

/// `sentinel resume` — clear the global pause flag.
func cmdResume(_ db: Database) throws {
    try db.execute("DELETE FROM kv WHERE key=?", SentinelCore.pausedKey)
    exit(0)
}

/// `sentinel emergency-exit <reason>`
///
/// Releases every active commitment, sets the global pause flag, logs
/// the exit, and inserts a row in emergency_exits so we can compute
/// monthly budget usage. The monthly budget enforcement itself is a
/// future verb (`emergency-budget`); for now we just record.
func cmdEmergencyExit(_ db: Database, _ args: [String]) throws {
    guard let reason = args.first, !reason.isEmpty else {
        usageError("emergency-exit <reason>")
    }
    let t = now()
    let active = try db.query(
        "SELECT id FROM commitments WHERE released_at IS NULL AND until_ts > ?", t)
    let releasedCount = active.count

    try db.execute(
        "UPDATE commitments SET released_at=? WHERE released_at IS NULL AND until_ts > ?",
        t, t)

    // Pause everything so any in-flight tick exits next iteration.
    try db.execute("""
        INSERT INTO kv (key, value, updated_at) VALUES (?, 'true', ?)
        ON CONFLICT(key) DO UPDATE SET value='true', updated_at=excluded.updated_at
    """, SentinelCore.pausedKey, t)

    try db.execute(
        "INSERT INTO log (ts, source, event, payload) VALUES (?, 'user', 'emergency_exit', ?)",
        t, "{\"reason\":\"\(reason.replacingOccurrences(of: "\"", with: "\\\""))\"}")

    try db.execute(
        "INSERT INTO emergency_exits (ts, reason, released_count) VALUES (?, ?, ?)",
        t, reason, releasedCount)

    print("released_count=\(releasedCount)")
    exit(0)
}

/// `sentinel world` — print the latest world snapshot as JSON.
func cmdWorld(_ db: Database) throws {
    if let row = try db.queryFirst(
        "SELECT * FROM world ORDER BY ts DESC LIMIT 1") {
        printJSON(rowToJSONValue(row))
    } else {
        print("{}")
    }
    exit(0)
}

/// `sentinel running` — print the running table as a JSON array.
func cmdRunning(_ db: Database) throws {
    let rows = try db.query("SELECT * FROM running ORDER BY started_at DESC")
    let arr = rows.map { rowToJSONValue($0) }
    printJSON(arr)
    exit(0)
}
