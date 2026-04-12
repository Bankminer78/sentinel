// DB.swift — thin wrapper around the SQLite3 C API.
//
// Why direct C API instead of GRDB or SQLite.swift: we ship a CLI binary
// AND a GUI app from the same package, both touching the same database
// concurrently. Vendor dependencies want a managed connection pool that
// fights cross-process access. The C API is unceremonious, ~150 lines,
// no external dependencies, and SQLite's own file locking is the
// concurrency primitive. WAL mode + busy_timeout handles the multi-
// writer case.

import Foundation
import SQLite3

// SQLite ships these as macros, which Swift doesn't import.
let SQLITE_TRANSIENT = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

public enum DBError: Error, CustomStringConvertible {
    case openFailed(Int32, String)
    case prepareFailed(Int32, String)
    case stepFailed(Int32, String)
    case noColumn(String)

    public var description: String {
        switch self {
        case .openFailed(let rc, let msg):    return "sqlite open failed (\(rc)): \(msg)"
        case .prepareFailed(let rc, let msg): return "sqlite prepare failed (\(rc)): \(msg)"
        case .stepFailed(let rc, let msg):    return "sqlite step failed (\(rc)): \(msg)"
        case .noColumn(let name):             return "no such column: \(name)"
        }
    }
}

public final class Database {
    private var handle: OpaquePointer?
    private static var instance: Database?
    private static let instanceLock = NSLock()

    /// Returns the process-wide shared Database. The first caller opens
    /// the file and runs migrations; subsequent callers in the same
    /// process share the connection.
    public static func shared() throws -> Database {
        instanceLock.lock()
        defer { instanceLock.unlock() }
        if let inst = instance { return inst }
        let inst = try Database(path: defaultPath())
        instance = inst
        return inst
    }

    /// Open a database at an arbitrary path. Used in tests; production
    /// callers should use ``shared()``.
    public init(path: URL) throws {
        try FileManager.default.createDirectory(
            at: path.deletingLastPathComponent(),
            withIntermediateDirectories: true)
        var h: OpaquePointer?
        let rc = sqlite3_open(path.path, &h)
        guard rc == SQLITE_OK, let h = h else {
            let msg = h.map { String(cString: sqlite3_errmsg($0)) } ?? "unknown"
            sqlite3_close(h)
            throw DBError.openFailed(rc, msg)
        }
        self.handle = h
        try execute("PRAGMA journal_mode=WAL")
        try execute("PRAGMA synchronous=NORMAL")
        try execute("PRAGMA busy_timeout=5000")
        try execute("PRAGMA foreign_keys=ON")
        try migrate()
    }

    deinit {
        if let h = handle {
            sqlite3_close(h)
        }
    }

    /// `~/Library/Application Support/Sentinel/sentinel.db`
    public static func defaultPath() -> URL {
        let appSupport = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first!
        return appSupport
            .appendingPathComponent("Sentinel", isDirectory: true)
            .appendingPathComponent("sentinel.db")
    }

    // MARK: - Execute / query

    /// Run a statement that returns no rows. Variadic args bind by index.
    public func execute(_ sql: String, _ args: Any?...) throws {
        try executeArr(sql, args)
    }

    public func executeArr(_ sql: String, _ args: [Any?]) throws {
        let stmt = try prepare(sql)
        defer { sqlite3_finalize(stmt) }
        try bind(stmt, args)
        let rc = sqlite3_step(stmt)
        guard rc == SQLITE_DONE || rc == SQLITE_ROW else {
            throw DBError.stepFailed(rc, errmsg())
        }
    }

    /// Run a statement and return all rows.
    public func query(_ sql: String, _ args: Any?...) throws -> [Row] {
        return try queryArr(sql, args)
    }

    public func queryArr(_ sql: String, _ args: [Any?]) throws -> [Row] {
        let stmt = try prepare(sql)
        defer { sqlite3_finalize(stmt) }
        try bind(stmt, args)
        var rows: [Row] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            rows.append(Row(stmt: stmt))
        }
        return rows
    }

    public func queryFirst(_ sql: String, _ args: Any?...) throws -> Row? {
        return try queryArr(sql, args).first
    }

    public func lastInsertRowID() -> Int64 {
        return sqlite3_last_insert_rowid(handle)
    }

    public func changes() -> Int32 {
        return sqlite3_changes(handle)
    }

    // MARK: - Internals

    private func prepare(_ sql: String) throws -> OpaquePointer? {
        var stmt: OpaquePointer?
        let rc = sqlite3_prepare_v2(handle, sql, -1, &stmt, nil)
        guard rc == SQLITE_OK else {
            throw DBError.prepareFailed(rc, errmsg())
        }
        return stmt
    }

    private func bind(_ stmt: OpaquePointer?, _ args: [Any?]) throws {
        for (i, arg) in args.enumerated() {
            let idx = Int32(i + 1)
            switch arg {
            case nil:
                sqlite3_bind_null(stmt, idx)
            case let v as Int:
                sqlite3_bind_int64(stmt, idx, Int64(v))
            case let v as Int32:
                sqlite3_bind_int64(stmt, idx, Int64(v))
            case let v as Int64:
                sqlite3_bind_int64(stmt, idx, v)
            case let v as Double:
                sqlite3_bind_double(stmt, idx, v)
            case let v as Float:
                sqlite3_bind_double(stmt, idx, Double(v))
            case let v as Bool:
                sqlite3_bind_int64(stmt, idx, v ? 1 : 0)
            case let v as String:
                sqlite3_bind_text(stmt, idx, v, -1, SQLITE_TRANSIENT)
            case let v as Data:
                _ = v.withUnsafeBytes { bytes in
                    sqlite3_bind_blob(stmt, idx, bytes.baseAddress, Int32(v.count), SQLITE_TRANSIENT)
                }
            default:
                // Last resort: stringify whatever it is.
                sqlite3_bind_text(stmt, idx, String(describing: arg!), -1, SQLITE_TRANSIENT)
            }
        }
    }

    private func errmsg() -> String {
        guard let h = handle else { return "no handle" }
        return String(cString: sqlite3_errmsg(h))
    }
}

// MARK: - Row

/// A single result row. Columns are indexed by name (the column name in
/// the SELECT, including aliases).
public struct Row {
    public let columns: [String: Any]

    init(stmt: OpaquePointer?) {
        let count = sqlite3_column_count(stmt)
        var dict: [String: Any] = [:]
        for i in 0..<count {
            let name = String(cString: sqlite3_column_name(stmt, i))
            let type = sqlite3_column_type(stmt, i)
            switch type {
            case SQLITE_INTEGER:
                dict[name] = sqlite3_column_int64(stmt, i)
            case SQLITE_FLOAT:
                dict[name] = sqlite3_column_double(stmt, i)
            case SQLITE_TEXT:
                if let cstr = sqlite3_column_text(stmt, i) {
                    dict[name] = String(cString: cstr)
                }
            case SQLITE_BLOB:
                if let bytes = sqlite3_column_blob(stmt, i) {
                    let count = Int(sqlite3_column_bytes(stmt, i))
                    dict[name] = Data(bytes: bytes, count: count)
                }
            default:
                break // SQLITE_NULL → omit
            }
        }
        self.columns = dict
    }

    public func string(_ name: String) -> String? {
        if let s = columns[name] as? String { return s }
        if let i = columns[name] as? Int64 { return String(i) }
        if let d = columns[name] as? Double { return String(d) }
        return nil
    }

    public func int(_ name: String) -> Int64? {
        if let i = columns[name] as? Int64 { return i }
        if let s = columns[name] as? String { return Int64(s) }
        return nil
    }

    public func double(_ name: String) -> Double? {
        if let d = columns[name] as? Double { return d }
        if let i = columns[name] as? Int64 { return Double(i) }
        if let s = columns[name] as? String { return Double(s) }
        return nil
    }

    public func bool(_ name: String) -> Bool {
        if let i = int(name) { return i != 0 }
        if let s = string(name)?.lowercased() {
            return s == "true" || s == "1" || s == "yes"
        }
        return false
    }
}

// MARK: - Schema migration

extension Database {
    private func migrate() throws {
        let schema = """
        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS log (
            id INTEGER PRIMARY KEY,
            ts REAL NOT NULL,
            source TEXT NOT NULL,
            event TEXT NOT NULL,
            payload TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_log_ts ON log(ts);

        CREATE TABLE IF NOT EXISTS commitments (
            id INTEGER PRIMARY KEY,
            kind TEXT NOT NULL,
            target TEXT,
            until_ts REAL NOT NULL,
            friction TEXT,
            released_at REAL,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_commitments_kind_target
            ON commitments(kind, target, released_at);

        CREATE TABLE IF NOT EXISTS running (
            name TEXT PRIMARY KEY,
            pid INTEGER NOT NULL,
            started_at REAL NOT NULL,
            last_heartbeat REAL NOT NULL,
            status_text TEXT
        );

        CREATE TABLE IF NOT EXISTS world (
            ts REAL PRIMARY KEY,
            windows TEXT NOT NULL,
            foreground_app TEXT,
            foreground_window TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_world_ts ON world(ts);

        CREATE TABLE IF NOT EXISTS emergency_exits (
            id INTEGER PRIMARY KEY,
            ts REAL NOT NULL,
            reason TEXT NOT NULL,
            released_count INTEGER NOT NULL DEFAULT 0
        );
        """
        // executescript-equivalent: split on ';' and execute one at a time
        // since sqlite3_prepare_v2 only handles one statement.
        for raw in schema.components(separatedBy: ";") {
            let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty { continue }
            try execute(trimmed)
        }
    }
}
