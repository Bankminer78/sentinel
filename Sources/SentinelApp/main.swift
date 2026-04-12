// SentinelApp — phase 2 standalone runner.
//
// Phase 3 replaces this with a real SwiftUI menu bar app. For now, this
// just instantiates the WorldRecorder and runs it for ~6 seconds so the
// recorder can be smoke-tested without the GUI scaffolding.
import Foundation
import SentinelCore

print("SentinelApp \(SentinelCore.version) — phase 2 recorder smoke test")

let db: Database
do {
    db = try Database.shared()
} catch {
    fputs("failed to open db: \(error)\n", stderr)
    exit(1)
}

let recorder = WorldRecorder(db: db, intervalS: 1.0)
recorder.start()
print("recorder started, will run for 6s")
Thread.sleep(forTimeInterval: 6.5)
recorder.stop()
print("recorder stopped")
