// LockListView.swift — sidebar list of installed locks plus the
// fixed Chat / Activity entries at the top.

import SwiftUI

struct LockListView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var processManager: ProcessManager

    var body: some View {
        List(selection: Binding(
            get: { state.route },
            set: { if let r = $0 { state.route = r } }
        )) {
            Label("Chat", systemImage: "bubble.left.fill")
                .tag(AppState.Route.chat)

            Label("Activity", systemImage: "list.bullet.rectangle")
                .tag(AppState.Route.activity)

            Section("Locks") {
                if state.locks.isEmpty {
                    Text("No locks installed yet")
                        .foregroundStyle(.secondary)
                        .italic()
                } else {
                    ForEach(state.locks) { lock in
                        LockRow(lock: lock)
                            .tag(AppState.Route.lock(lock.name))
                    }
                }
            }
        }
        .listStyle(.sidebar)
    }
}

private struct LockRow: View {
    let lock: LockEntry
    @EnvironmentObject var processManager: ProcessManager
    @EnvironmentObject var state: AppState

    var body: some View {
        HStack(spacing: 8) {
            statusDot
            VStack(alignment: .leading, spacing: 1) {
                Text(lock.displayName)
                    .lineLimit(1)
                if let info = state.runningByName[lock.name] {
                    if let s = info.statusText, !s.isEmpty {
                        Text(s)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }
            }
            Spacer(minLength: 0)
        }
    }

    private var statusDot: some View {
        let isLocallyRunning = processManager.isRunning(lock.name)
        let isFresh = state.runningByName[lock.name]?.isFresh == true
        let color: Color
        if isLocallyRunning || isFresh {
            color = .green
        } else if state.runningByName[lock.name] != nil {
            color = .yellow
        } else {
            color = .gray.opacity(0.4)
        }
        return Circle()
            .fill(color)
            .frame(width: 8, height: 8)
    }
}
