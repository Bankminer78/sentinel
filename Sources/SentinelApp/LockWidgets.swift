// LockWidgets.swift — the SwiftUI views rendered in the Dashboard tab
// of LockDetailView. The tab's widget is chosen by the lock's
// declarative `ui=<type>` header; the dispatch lives in DashboardView.
//
// Widgets own their own polling — they open Database.shared() directly
// and read kv / running / log rows every second. Cheap because SQLite
// reads on a local file are sub-millisecond and we only render when the
// value actually changed.

import SwiftUI
import SentinelCore

// MARK: - Dispatch

struct DashboardView: View {
    let lock: LockEntry
    @EnvironmentObject var state: AppState
    @EnvironmentObject var processManager: ProcessManager

    var body: some View {
        switch lock.ui {
        case .status:
            StatusWidget(lock: lock)
        case .quota(let key, let limit):
            QuotaWidget(lock: lock, quotaKey: key, quotaLimitS: limit)
        }
    }
}

// MARK: - Quota widget

/// Progress ring + live countdown for locks that track a daily quota in
/// the sentinel kv store. The ring fills clockwise as you use the quota;
/// center text shows the remaining time.
struct QuotaWidget: View {
    let lock: LockEntry
    let quotaKey: String        // e.g. "quota:distractions:used_s"
    let quotaLimitS: Int        // e.g. 1200 (20 minutes)

    @State private var usedS: Int = 0
    @State private var date: String = ""
    @State private var lastLogs: [LogRow] = []
    @State private var timer: Timer?

    private var remainingS: Int { max(0, quotaLimitS - usedS) }
    private var fraction: Double {
        guard quotaLimitS > 0 else { return 0 }
        return min(1.0, Double(usedS) / Double(quotaLimitS))
    }

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            ring
                .frame(width: 260, height: 260)
                .padding(.vertical, 32)
            statBar
                .padding(.horizontal, 40)
            Spacer()
            logTail
                .padding(.horizontal, 40)
                .padding(.bottom, 24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { start() }
        .onDisappear { stop() }
    }

    // MARK: subviews

    private var ring: some View {
        ZStack {
            Circle()
                .stroke(Color.gray.opacity(0.15), lineWidth: 14)
            Circle()
                .trim(from: 0, to: fraction)
                .stroke(ringColor,
                        style: StrokeStyle(lineWidth: 14, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(.smooth(duration: 0.6), value: fraction)
            VStack(spacing: 6) {
                Text(fmtTime(remainingS))
                    .font(.system(size: 56, weight: .light, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(ringColor)
                Text(headline)
                    .font(.caption)
                    .textCase(.uppercase)
                    .foregroundStyle(.secondary)
                    .tracking(1)
            }
        }
    }

    private var statBar: some View {
        HStack(spacing: 24) {
            StatColumn(label: "used today", value: fmtTime(usedS))
            Divider().frame(height: 32)
            StatColumn(label: "daily quota", value: fmtTime(quotaLimitS))
            Divider().frame(height: 32)
            StatColumn(label: "resets at", value: "midnight")
        }
        .frame(maxWidth: .infinity)
    }

    private var logTail: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("recent activity")
                .font(.caption)
                .textCase(.uppercase)
                .foregroundStyle(.tertiary)
                .tracking(1)
            if lastLogs.isEmpty {
                Text("nothing yet")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .italic()
            } else {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(lastLogs) { row in
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text(fmtAbsoluteTime(row.ts))
                                .font(.system(.caption2, design: .monospaced))
                                .foregroundStyle(.tertiary)
                                .frame(width: 60, alignment: .leading)
                            Text(row.event)
                                .font(.caption)
                                .foregroundStyle(colorForEvent(row.event))
                                .frame(width: 80, alignment: .leading)
                            Text(row.payload ?? "")
                                .font(.system(.caption, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                                .truncationMode(.tail)
                        }
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: derived

    private var ringColor: Color {
        if remainingS <= 0 { return .red }
        if Double(remainingS) < Double(quotaLimitS) * 0.25 { return .orange }
        return .green
    }

    private var headline: String {
        if remainingS <= 0 { return "quota exhausted" }
        return "left today"
    }

    private func colorForEvent(_ event: String) -> Color {
        switch event {
        case "blocked": return .red
        case "used":    return .orange
        case "daily_reset", "engaged": return .blue
        case "stopped", "expired":     return .secondary
        default: return .primary
        }
    }

    // MARK: polling

    private func start() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            refresh()
        }
    }

    private func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func refresh() {
        guard let db = try? Database.shared() else { return }
        let usedRow = try? db.queryFirst(
            "SELECT value FROM kv WHERE key=?", quotaKey)
        let dateRow = try? db.queryFirst(
            "SELECT value FROM kv WHERE key=?",
            quotaKey.replacingOccurrences(of: ":used_s", with: ":date"))
        let logRows = (try? db.query(
            "SELECT * FROM log WHERE source=? ORDER BY ts DESC LIMIT 6",
            lock.name)) ?? []

        let newUsed = Int(usedRow?.string("value") ?? "0") ?? 0
        let newDate = dateRow?.string("value") ?? ""
        let newLogs = logRows.compactMap { LogRow($0) }

        // Only trigger SwiftUI updates when something actually changed.
        if newUsed != usedS || newDate != date {
            usedS = newUsed
            date = newDate
        }
        if newLogs.map(\.id) != lastLogs.map(\.id) {
            lastLogs = newLogs
        }
    }
}

// MARK: - Status widget (default)

/// The generic dashboard for locks that didn't declare `ui=`. Shows the
/// running.status_text big + last 10 log entries + engaged/not.
struct StatusWidget: View {
    let lock: LockEntry
    @EnvironmentObject var state: AppState
    @EnvironmentObject var processManager: ProcessManager
    @State private var lastLogs: [LogRow] = []
    @State private var timer: Timer?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Spacer()
            statusCard
                .frame(maxWidth: .infinity)
                .padding(.horizontal, 40)
            Spacer()
            logTail
                .padding(.horizontal, 40)
                .padding(.bottom, 24)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { start() }
        .onDisappear { stop() }
    }

    private var statusCard: some View {
        VStack(spacing: 12) {
            if let info = state.runningByName[lock.name] {
                HStack(spacing: 8) {
                    Circle().fill(.green).frame(width: 10, height: 10)
                    Text("running")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textCase(.uppercase)
                        .tracking(1)
                }
                Text(info.statusText ?? "…")
                    .font(.system(size: 42, weight: .light, design: .rounded))
                    .monospacedDigit()
                    .multilineTextAlignment(.center)
                    .lineLimit(2)
                Text("pid \(info.pid) · started \(fmtRelative(info.startedAt))")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .monospacedDigit()
            } else {
                HStack(spacing: 8) {
                    Circle().fill(Color.gray.opacity(0.4))
                        .frame(width: 10, height: 10)
                    Text("idle")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textCase(.uppercase)
                        .tracking(1)
                }
                Text("Not engaged")
                    .font(.system(size: 34, weight: .light, design: .rounded))
                    .foregroundStyle(.secondary)
                Text("click Run above to start")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .padding(24)
        .background(Color(nsColor: .windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var logTail: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("recent activity")
                .font(.caption)
                .textCase(.uppercase)
                .foregroundStyle(.tertiary)
                .tracking(1)
            if lastLogs.isEmpty {
                Text("no events yet")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .italic()
            } else {
                ForEach(lastLogs) { row in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(fmtAbsoluteTime(row.ts))
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundStyle(.tertiary)
                            .frame(width: 60, alignment: .leading)
                        Text(row.event)
                            .font(.caption)
                            .frame(width: 120, alignment: .leading)
                        Text(row.payload ?? "")
                            .font(.system(.caption, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.tail)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func start() {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
            refresh()
        }
    }

    private func stop() {
        timer?.invalidate()
        timer = nil
    }

    private func refresh() {
        guard let db = try? Database.shared() else { return }
        let rows = (try? db.query(
            "SELECT * FROM log WHERE source=? ORDER BY ts DESC LIMIT 10",
            lock.name)) ?? []
        let logs = rows.compactMap { LogRow($0) }
        if logs.map(\.id) != lastLogs.map(\.id) {
            lastLogs = logs
        }
    }
}

// MARK: - Shared bits

struct StatColumn: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.title3)
                .monospacedDigit()
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
                .tracking(0.8)
        }
        .frame(maxWidth: .infinity)
    }
}

func fmtTime(_ s: Int) -> String {
    if s <= 0 { return "0:00" }
    let m = s / 60
    let sec = s % 60
    if m >= 60 {
        let h = m / 60
        let rm = m % 60
        return "\(h):\(String(format: "%02d", rm)):\(String(format: "%02d", sec))"
    }
    return "\(m):\(String(format: "%02d", sec))"
}

func fmtAbsoluteTime(_ ts: Double) -> String {
    let f = DateFormatter()
    f.dateFormat = "HH:mm:ss"
    return f.string(from: Date(timeIntervalSince1970: ts))
}

func fmtRelative(_ ts: Double) -> String {
    let d = Date().timeIntervalSince1970 - ts
    if d < 60 { return "\(Int(d))s ago" }
    if d < 3600 { return "\(Int(d / 60))m ago" }
    return "\(Int(d / 3600))h ago"
}
