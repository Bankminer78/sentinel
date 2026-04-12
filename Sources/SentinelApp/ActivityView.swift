// ActivityView.swift — recent rows from the log table.
//
// Polled from disk every 1.5s via a Timer; the AppDelegate's existing
// refresh loop already runs but doesn't touch the log, so this view
// owns its own polling. Cheap because the query is `SELECT ... LIMIT 200`.

import SwiftUI
import SentinelCore

struct ActivityView: View {
    @State private var rows: [LogRow] = []
    @State private var timer: Timer?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Activity")
                    .font(.title2).bold()
                Spacer()
                Text("\(rows.count) events")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button {
                    refresh()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.plain)
            }
            .padding()

            Divider()

            if rows.isEmpty {
                VStack(spacing: 6) {
                    Image(systemName: "list.bullet.rectangle")
                        .font(.system(size: 36))
                        .foregroundStyle(.secondary)
                    Text("No activity yet")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(rows) { row in
                    LogRowCell(row: row)
                }
                .listStyle(.plain)
                .textSelection(.enabled)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear {
            refresh()
            timer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { _ in
                refresh()
            }
        }
        .onDisappear {
            timer?.invalidate()
            timer = nil
        }
    }

    private func refresh() {
        rows = Controls.recentLog(limit: 200)
    }
}

extension LogRow: Identifiable {}

private struct LogRowCell: View {
    let row: LogRow

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(formatTime(row.ts))
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .frame(width: 70, alignment: .leading)
            Text(row.source)
                .font(.caption.bold())
                .foregroundStyle(.tint)
                .frame(width: 120, alignment: .leading)
                .lineLimit(1)
            Text(row.event)
                .font(.caption)
                .frame(width: 140, alignment: .leading)
                .lineLimit(1)
            Text(row.payload ?? "")
                .font(.system(.caption, design: .monospaced))
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.tail)
        }
        .padding(.vertical, 2)
    }

    private func formatTime(_ ts: Double) -> String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f.string(from: Date(timeIntervalSince1970: ts))
    }
}
