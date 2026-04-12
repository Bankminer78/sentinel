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
            ChatView()
        case .activity:
            ActivityView()
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
        SidebarFooter()
    }
}

/// Sidebar footer: pause/resume + emergency exit + version. Polls the
/// pause state from the db every 1s so the button label reflects what
/// the CLI / other clients did.
private struct SidebarFooter: View {
    @EnvironmentObject var processManager: ProcessManager
    @State private var paused: Bool = Controls.isPaused()
    @State private var pollTimer: Timer?
    @State private var showEmergencyConfirm: Bool = false
    @State private var emergencyReason: String = ""
    @State private var lastEmergencyResult: String? = nil

    var body: some View {
        VStack(spacing: 6) {
            Divider()
            VStack(spacing: 6) {
                if paused {
                    Button {
                        Controls.resume()
                        paused = false
                    } label: {
                        Label("Resume locks", systemImage: "play.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.regular)
                    .tint(.green)
                } else {
                    Button {
                        Controls.pause()
                        processManager.stopAll()
                        paused = true
                    } label: {
                        Label("Pause all", systemImage: "pause.fill")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.regular)
                }

                Button(role: .destructive) {
                    showEmergencyConfirm = true
                } label: {
                    Label("Emergency exit", systemImage: "exclamationmark.triangle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.regular)

                if let r = lastEmergencyResult {
                    Text(r)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                Text("Sentinel v\(SentinelCore.version)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 10)
        }
        .onAppear {
            paused = Controls.isPaused()
            pollTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
                paused = Controls.isPaused()
            }
        }
        .onDisappear {
            pollTimer?.invalidate()
            pollTimer = nil
        }
        .alert("Emergency exit", isPresented: $showEmergencyConfirm) {
            TextField("reason (required)", text: $emergencyReason)
            Button("Cancel", role: .cancel) {
                emergencyReason = ""
            }
            Button("Confirm", role: .destructive) {
                let reason = emergencyReason.trimmingCharacters(in: .whitespacesAndNewlines)
                emergencyReason = ""
                guard !reason.isEmpty else { return }
                processManager.stopAll()
                let count = Controls.emergencyExit(reason: reason)
                lastEmergencyResult = "Released \(count) commitments. Locks paused."
                paused = true
            }
        } message: {
            Text("This releases every active commitment, sets the global pause flag, and SIGTERMs every running lock. Type a brief reason.")
        }
    }
}
