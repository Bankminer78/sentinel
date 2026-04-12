// ContentView.swift — top-level SwiftUI layout.
//
// Phase 3 is a stub. Phase 4 puts a real LockListView in the sidebar.
// Phase 5 puts a real ChatView in the content area. Phase 6 wires the
// pause/emergency buttons in the sidebar footer.

import SwiftUI
import SentinelCore

struct ContentView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        NavigationSplitView {
            SidebarPlaceholder()
                .frame(minWidth: 220, idealWidth: 240)
        } detail: {
            ContentPlaceholder()
        }
        .navigationTitle("Sentinel")
    }
}

struct SidebarPlaceholder: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("🛡 Sentinel")
                    .font(.title3)
                    .bold()
                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.top, 14)
            .padding(.bottom, 10)

            Divider()

            List {
                Label("Chat", systemImage: "bubble.left.fill")
                Label("Activity", systemImage: "list.bullet.rectangle")
            }
            .listStyle(.sidebar)

            Spacer()

            VStack(spacing: 6) {
                Text("Phase 3 — sidebar will fill in next")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(12)
        }
    }
}

struct ContentPlaceholder: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "shield.lefthalf.filled")
                .font(.system(size: 48))
                .foregroundStyle(.tint)
            Text("Sentinel")
                .font(.largeTitle)
                .bold()
            Text("v\(SentinelCore.version) — phase 3 stub")
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Text("Lock list lands in phase 4. Chat lands in phase 5.")
                .font(.caption)
                .foregroundStyle(.tertiary)
                .padding(.top, 8)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.windowBackgroundColor))
    }
}
