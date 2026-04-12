// Models.swift — typed views over the SQLite tables.
//
// Phase 1 only needs the tiny subset the CLI references; the GUI app
// will add more in Phase 4 as needed. Each model exposes a `from(row:)`
// constructor that adapts a generic `Row` into a concrete struct.

import Foundation

public enum SentinelCore {
    public static let version = "0.1.0"

    /// Pause flag key in the kv table.
    public static let pausedKey = "paused"

    /// Per-lock stop flag key (concatenated with the lock name).
    public static func stopKey(_ name: String) -> String { "stop:\(name)" }
}

public struct LogRow: Codable {
    public let id: Int64
    public let ts: Double
    public let source: String
    public let event: String
    public let payload: String?

    public init?(_ row: Row) {
        guard let id = row.int("id"),
              let ts = row.double("ts"),
              let source = row.string("source"),
              let event = row.string("event") else { return nil }
        self.id = id
        self.ts = ts
        self.source = source
        self.event = event
        self.payload = row.string("payload")
    }
}

public struct Commitment: Codable {
    public let id: Int64
    public let kind: String
    public let target: String?
    public let untilTs: Double
    public let friction: String?
    public let releasedAt: Double?
    public let createdAt: Double

    public init?(_ row: Row) {
        guard let id = row.int("id"),
              let kind = row.string("kind"),
              let untilTs = row.double("until_ts"),
              let createdAt = row.double("created_at") else { return nil }
        self.id = id
        self.kind = kind
        self.target = row.string("target")
        self.untilTs = untilTs
        self.friction = row.string("friction")
        self.releasedAt = row.double("released_at")
        self.createdAt = createdAt
    }
}

public struct RunningRow: Codable {
    public let name: String
    public let pid: Int64
    public let startedAt: Double
    public let lastHeartbeat: Double
    public let statusText: String?

    public init?(_ row: Row) {
        guard let name = row.string("name"),
              let pid = row.int("pid"),
              let startedAt = row.double("started_at"),
              let lastHeartbeat = row.double("last_heartbeat") else { return nil }
        self.name = name
        self.pid = pid
        self.startedAt = startedAt
        self.lastHeartbeat = lastHeartbeat
        self.statusText = row.string("status_text")
    }
}

public struct WorldRow: Codable {
    public let ts: Double
    public let windows: String         // JSON-encoded array
    public let foregroundApp: String?
    public let foregroundWindow: String?

    public init?(_ row: Row) {
        guard let ts = row.double("ts"),
              let windows = row.string("windows") else { return nil }
        self.ts = ts
        self.windows = windows
        self.foregroundApp = row.string("foreground_app")
        self.foregroundWindow = row.string("foreground_window")
    }
}
