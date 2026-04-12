// ProcessManager.swift — spawn lock scripts as real OS subprocesses,
// capture their stdout/stderr, and tear them down on Stop.
//
// This is the load-bearing piece of Phase 4. The whole reason the
// scripts-as-locks model works is that the OS process model gives us
// reliable signal-based control: SIGTERM stops a script cleanly, SIGKILL
// is the nuclear option, and there are no race conditions to fight.

import Foundation
import Darwin
import SwiftUI

final class ProcessManager: ObservableObject {
    /// Tail of recent stdout/stderr per running lock, keyed by lock name.
    /// Capped at OUTPUT_BUFFER_SIZE chars to avoid unbounded growth.
    @Published var output: [String: String] = [:]

    /// pid of each currently-spawned lock, keyed by name. Empty when
    /// the process has exited (or hasn't started).
    @Published var runningPIDs: [String: Int32] = [:]

    /// Wallclock when the process was launched, used for "running for Xs"
    /// display in the sidebar.
    @Published var startedAt: [String: Date] = [:]

    private var processes: [String: Process] = [:]
    private let outputLock = NSLock()
    private let OUTPUT_BUFFER_SIZE = 16 * 1024

    /// Path to the bundled `sentinel` CLI inside the .app's Resources/
    /// directory. Locks shell out to this path so the cross-lock features
    /// (`sentinel check`, `sentinel log`, etc.) work without the user
    /// having to symlink anything onto $PATH.
    private var bundledCLIDir: String? {
        if let url = Bundle.main.url(forResource: "sentinel", withExtension: nil) {
            return url.deletingLastPathComponent().path
        }
        return nil
    }

    func isRunning(_ name: String) -> Bool {
        runningPIDs[name] != nil
    }

    /// Spawn a lock script. Returns silently on success; prints to stderr
    /// and updates `output[name]` with an error message on failure.
    func run(lock: LockEntry) {
        // Stop a previous instance if there is one.
        stop(name: lock.name)

        let proc = Process()
        configureExecutable(proc, for: lock)

        // Augment PATH so the script can find `sentinel` without an
        // absolute path.
        var env = ProcessInfo.processInfo.environment
        if let dir = bundledCLIDir {
            env["PATH"] = "\(dir):\(env["PATH"] ?? "/usr/bin:/bin")"
        }
        // Tell the script its own logical name so `sentinel check "$NAME"`
        // can be a single line they don't have to derive.
        env["SENTINEL_LOCK_NAME"] = lock.name
        proc.environment = env

        let outPipe = Pipe()
        let errPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = errPipe

        let name = lock.name
        outPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            self?.appendOutput(name: name, data: handle.availableData)
        }
        errPipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            self?.appendOutput(name: name, data: handle.availableData)
        }

        proc.terminationHandler = { [weak self] p in
            DispatchQueue.main.async {
                outPipe.fileHandleForReading.readabilityHandler = nil
                errPipe.fileHandleForReading.readabilityHandler = nil
                self?.appendOutput(
                    name: name,
                    text: "\n[exited with status \(p.terminationStatus)]\n")
                self?.processes.removeValue(forKey: name)
                self?.runningPIDs.removeValue(forKey: name)
                self?.startedAt.removeValue(forKey: name)
            }
        }

        do {
            try proc.run()
            processes[name] = proc
            DispatchQueue.main.async {
                self.runningPIDs[name] = proc.processIdentifier
                self.startedAt[name] = Date()
                self.appendOutput(name: name,
                                  text: "[started — pid \(proc.processIdentifier)]\n")
            }
        } catch {
            appendOutput(name: name, text: "[failed to launch: \(error)]\n")
        }
    }

    /// SIGTERM the process. The script is expected to clean up and exit;
    /// if it doesn't, the user can `forceKill` it.
    func stop(name: String) {
        guard let proc = processes[name], proc.isRunning else { return }
        proc.terminate()
    }

    /// SIGKILL — the nuclear option for a stuck script.
    func forceKill(name: String) {
        guard let proc = processes[name], proc.isRunning else { return }
        Darwin.kill(proc.processIdentifier, SIGKILL)
    }

    /// SIGTERM every running lock at once.
    func stopAll() {
        for proc in processes.values where proc.isRunning {
            proc.terminate()
        }
    }

    // MARK: - Internals

    private func configureExecutable(_ proc: Process, for lock: LockEntry) {
        switch lock.language {
        case "sh":
            proc.executableURL = URL(fileURLWithPath: "/bin/bash")
            proc.arguments = [lock.path.path]
        case "py":
            // /usr/bin/env so the script's own #! handling works for
            // python3 / python depending on what's installed.
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            proc.arguments = ["python3", lock.path.path]
        case "swift":
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            proc.arguments = ["swift", lock.path.path]
        case "rb":
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            proc.arguments = ["ruby", lock.path.path]
        case "js":
            proc.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            proc.arguments = ["node", lock.path.path]
        default:
            // Try executing the file directly — relies on its own shebang
            // and execute permissions.
            proc.executableURL = lock.path
        }
    }

    private func appendOutput(name: String, data: Data) {
        guard !data.isEmpty,
              let str = String(data: data, encoding: .utf8) else { return }
        appendOutput(name: name, text: str)
    }

    private func appendOutput(name: String, text: String) {
        outputLock.lock()
        var current = output[name] ?? ""
        current += text
        if current.count > OUTPUT_BUFFER_SIZE {
            current = String(current.suffix(OUTPUT_BUFFER_SIZE))
        }
        outputLock.unlock()
        DispatchQueue.main.async {
            self.output[name] = current
        }
    }
}
