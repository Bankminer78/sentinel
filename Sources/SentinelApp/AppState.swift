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

    /// Optional dashboard. If a file named `<name>.html` exists next to
    /// the lock script, it becomes the Dashboard tab's content. Claude
    /// authors it alongside the script. No config needed — the sibling
    /// file IS the config.
    let dashboardURL: URL?

    var id: String { name }
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
