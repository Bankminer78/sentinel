// AppState.swift — observable shared state for the SwiftUI tree.
//
// Phase 3 ships a stub. Phases 4-6 will populate it with the live
// lock list (parsed from the locks directory), the running map
// (polled from the running table), and the global pause flag.

import Foundation
import SwiftUI

final class AppState: ObservableObject {
    @Published var locks: [LockEntry] = []
    @Published var runningByName: [String: RunningInfo] = [:]
    @Published var paused: Bool = false
    @Published var route: Route = .chat

    enum Route: Hashable {
        case chat
        case lock(String)   // lock name
        case activity
    }
}

/// One installed lock — a script file in `~/Library/Application Support/Sentinel/locks/`.
struct LockEntry: Identifiable, Equatable {
    let name: String          // file basename without extension
    let filename: String      // including extension (.sh / .py / .swift)
    let path: URL
    let displayName: String   // from "# sentinel: name=" header, falls back to filename
    let description: String   // from header
    let language: String      // sh / python / swift / unknown
    let ui: LockUI            // what widget renders on the Dashboard tab

    var id: String { name }
}

/// A lock's optional Dashboard widget, declared in its header comments
/// via `# sentinel: ui=<type>` plus widget-specific keys. Unknown or
/// missing ui declarations fall back to `.status` — a generic card
/// showing the lock's live status_text + recent log entries.
enum LockUI: Equatable {
    /// Generic — shows the running.status_text prominently + recent logs.
    case status

    /// Progress ring + time remaining / used. Keys:
    ///   quota_key    — kv key holding the "used seconds" counter
    ///   quota_limit  — daily quota in seconds
    case quota(key: String, limitS: Int)

    /// Parse from the flat header dict (e.g. {"ui": "quota",
    /// "quota_key": "quota:distractions:used_s", "quota_limit": "1200"}).
    static func from(header: [String: String]) -> LockUI {
        switch header["ui"]?.lowercased() {
        case "quota":
            guard let k = header["quota_key"], !k.isEmpty,
                  let s = header["quota_limit"],
                  let limit = Int(s), limit > 0 else {
                return .status
            }
            return .quota(key: k, limitS: limit)
        default:
            return .status
        }
    }
}

/// Live status of a running lock — joined from the `running` table.
struct RunningInfo: Equatable {
    let pid: Int64
    let startedAt: Double
    let lastHeartbeat: Double
    let statusText: String?

    /// True if last heartbeat was within 10 seconds.
    var isFresh: Bool {
        Date().timeIntervalSince1970 - lastHeartbeat < 10
    }
}
