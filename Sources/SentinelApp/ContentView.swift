// ContentView.swift — top-level SwiftUI layout.

import SwiftUI
import SentinelCore

struct ContentView: View {
    @EnvironmentObject var state: AppState
    @EnvironmentObject var processManager: ProcessManager

    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                LockListView()
                    .frame(minWidth: 220, idealWidth: 240)
                Spacer(minLength: 0)
                sidebarFooter
            }
        } detail: {
            content
        }
        .navigationTitle("Sentinel")
    }

    @ViewBuilder
    private var content: some View {
        switch state.route {
        case .chat:
            ChatPlaceholder()
        case .activity:
            ActivityPlaceholder()
        case .lock(let name):
            if let lock = state.locks.first(where: { $0.name == name }) {
                LockDetailView(lock: lock)
            } else {
                Text("Lock not found").foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
    }

    private var sidebarFooter: some View {
        VStack(spacing: 6) {
            Divider()
            Text("Sentinel v\(SentinelCore.version)")
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .padding(.bottom, 10)
    }
}

private struct ChatPlaceholder: View {
    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "bubble.left.and.bubble.right.fill")
                .font(.system(size: 48))
                .foregroundStyle(.tint)
            Text("Chat coming in phase 5")
                .font(.title3)
            Text("Phase 5 wires this up to the Claude Messages API.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

private struct ActivityPlaceholder: View {
    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "list.bullet.rectangle")
                .font(.system(size: 48))
                .foregroundStyle(.tint)
            Text("Activity log")
                .font(.title3)
            Text("Phase 6 reads the log table from the shared db.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
