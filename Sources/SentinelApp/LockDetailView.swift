// LockDetailView.swift — script source + Run/Stop/Force-kill buttons
// + live stdout panel for one selected lock.

import SwiftUI

struct LockDetailView: View {
    let lock: LockEntry
    @EnvironmentObject var processManager: ProcessManager
    @EnvironmentObject var state: AppState

    @State private var sourceText: String = ""
    @State private var selectedTab: DetailTab = .dashboard
    @State private var showDeleteConfirm: Bool = false

    enum DetailTab: String, CaseIterable, Identifiable {
        case dashboard = "Dashboard"
        case output    = "Output"
        case source    = "Source"
        var id: String { rawValue }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
            Divider()
            controls
            Divider()
            tabs
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { loadSource() }
        .onChange(of: lock.path) { _ in
            loadSource()
            selectedTab = .output
        }
        .alert("Delete \(lock.displayName)?",
               isPresented: $showDeleteConfirm) {
            Button("Cancel", role: .cancel) { }
            Button("Delete", role: .destructive) { deleteLock() }
        } message: {
            Text("The script file will be moved to the trash. You can restore it from there.")
        }
    }

    // MARK: - Subviews

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(lock.displayName)
                .font(.title2)
                .bold()
            if !lock.description.isEmpty {
                Text(lock.description)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 12) {
                Label(lock.filename, systemImage: "doc.text")
                Label(lock.language, systemImage: "chevron.left.forwardslash.chevron.right")
                if processManager.isRunning(lock.name) {
                    Label("running", systemImage: "play.fill")
                        .foregroundStyle(.green)
                } else if state.runningByName[lock.name]?.isFresh == true {
                    Label("running (other process)", systemImage: "play.fill")
                        .foregroundStyle(.green)
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding()
    }

    private var controls: some View {
        HStack(spacing: 8) {
            Button {
                processManager.run(lock: lock)
            } label: {
                Label("Run", systemImage: "play.fill")
            }
            .buttonStyle(.borderedProminent)
            .disabled(processManager.isRunning(lock.name))

            Button {
                processManager.stop(name: lock.name)
            } label: {
                Label("Stop", systemImage: "stop.fill")
            }
            .disabled(!processManager.isRunning(lock.name))

            Button {
                processManager.forceKill(name: lock.name)
            } label: {
                Label("Force kill", systemImage: "xmark.octagon.fill")
            }
            .disabled(!processManager.isRunning(lock.name))

            Spacer()

            Button(role: .destructive) {
                showDeleteConfirm = true
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
    }

    private var tabs: some View {
        VStack(spacing: 0) {
            Picker("", selection: $selectedTab) {
                ForEach(DetailTab.allCases) { t in
                    Text(t.rawValue).tag(t)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal)
            .padding(.top, 8)

            switch selectedTab {
            case .dashboard: DashboardView(lock: lock)
            case .output:    outputView
            case .source:    sourceView
            }
        }
    }

    private var outputView: some View {
        ScrollView {
            Text(processManager.output[lock.name] ?? "(no output yet)")
                .font(.system(.callout, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
                .padding()
        }
        .background(Color(nsColor: .textBackgroundColor))
    }

    private var sourceView: some View {
        ScrollView {
            Text(sourceText)
                .font(.system(.callout, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
                .padding()
        }
        .background(Color(nsColor: .textBackgroundColor))
    }

    // MARK: - Actions

    private func loadSource() {
        sourceText = (try? String(contentsOf: lock.path, encoding: .utf8)) ?? "(failed to read file)"
    }

    private func deleteLock() {
        processManager.stop(name: lock.name)
        do {
            try FileManager.default.trashItem(at: lock.path, resultingItemURL: nil)
        } catch {
            // Last resort: just unlink it
            try? FileManager.default.removeItem(at: lock.path)
        }
        // Refresh + leave the lock view
        state.locks = LockStore.listLocks()
        state.route = .chat
    }
}
