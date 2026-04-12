// LockStore.swift — read lock script files from the locks directory.
//
// A "lock" is any executable file in `~/Library/Application Support/
// Sentinel/locks/` whose extension we recognize (.sh, .py, .swift, .rb,
// .js — anything we know how to invoke). The first ~12 lines of each
// file are scanned for header lines like:
//
//     # sentinel: name="YouTube or TextEdit"
//     # sentinel: description="Lock to YouTube + TextEdit for 2m"
//
// or the equivalent with `//` for Swift / JS. Whatever we find populates
// the LockEntry display data; everything is optional.

import Foundation

enum LockStore {
    static let locksDir: URL = {
        FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)
            .first!
            .appendingPathComponent("Sentinel", isDirectory: true)
            .appendingPathComponent("locks", isDirectory: true)
    }()

    static func ensureDirExists() {
        try? FileManager.default.createDirectory(
            at: locksDir, withIntermediateDirectories: true)
    }

    /// Copy bundled examples into the user's locks directory if it's
    /// empty. Idempotent — once the user has any locks installed, this
    /// is a no-op so we don't keep restoring deleted examples.
    static func seedExamplesIfEmpty() {
        ensureDirExists()
        let fm = FileManager.default
        let existing = (try? fm.contentsOfDirectory(atPath: locksDir.path)) ?? []
        let visible = existing.filter { !$0.hasPrefix(".") }
        guard visible.isEmpty else { return }

        guard let examplesDir = Bundle.main.url(
            forResource: "examples", withExtension: nil) else {
            // Running outside of the .app bundle (e.g. `swift run`).
            // Try the project's examples/locks/ instead.
            let cwdExamples = URL(fileURLWithPath: fm.currentDirectoryPath)
                .appendingPathComponent("examples/locks", isDirectory: true)
            if fm.fileExists(atPath: cwdExamples.path) {
                copyExamples(from: cwdExamples)
            }
            return
        }
        copyExamples(from: examplesDir)
    }

    private static func copyExamples(from src: URL) {
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(
            at: src, includingPropertiesForKeys: nil) else { return }
        for entry in entries where !entry.lastPathComponent.hasPrefix(".") {
            let dst = locksDir.appendingPathComponent(entry.lastPathComponent)
            do {
                try fm.copyItem(at: entry, to: dst)
                // chmod +x
                try fm.setAttributes(
                    [.posixPermissions: 0o755], ofItemAtPath: dst.path)
            } catch {
                NSLog("[Sentinel] failed to seed example \(entry.lastPathComponent): \(error)")
            }
        }
    }

    static func listLocks() -> [LockEntry] {
        ensureDirExists()
        let fm = FileManager.default
        guard let entries = try? fm.contentsOfDirectory(
            at: locksDir,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else { return [] }

        var out: [LockEntry] = []
        for url in entries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            // Skip directories — locks are single files
            var isDir: ObjCBool = false
            fm.fileExists(atPath: url.path, isDirectory: &isDir)
            if isDir.boolValue { continue }

            let ext = url.pathExtension.lowercased()
            let language = languageFor(ext: ext)
            guard !language.isEmpty else { continue }

            let basename = url.deletingPathExtension().lastPathComponent
            let header = parseHeader(at: url)
            out.append(LockEntry(
                name: basename,
                filename: url.lastPathComponent,
                path: url,
                displayName: header["name"] ?? basename.replacingOccurrences(of: "_", with: " "),
                description: header["description"] ?? "",
                language: language
            ))
        }
        return out
    }

    /// Map a file extension to a language tag we know how to invoke.
    /// Empty string means we don't recognize it.
    static func languageFor(ext: String) -> String {
        switch ext {
        case "sh", "bash":     return "sh"
        case "py", "python":   return "py"
        case "swift":          return "swift"
        case "rb", "ruby":     return "rb"
        case "js", "mjs":      return "js"
        case "":               return "exec"   // bare executable
        default:               return ""
        }
    }

    /// Parse `# sentinel: key="value"` style header lines from the first
    /// ~12 lines of a script. Returns a flat dict.
    private static func parseHeader(at url: URL) -> [String: String] {
        guard let data = try? Data(contentsOf: url),
              let text = String(data: data.prefix(2048), encoding: .utf8)
        else { return [:] }

        var dict: [String: String] = [:]
        var lineCount = 0
        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            lineCount += 1
            if lineCount > 12 { break }
            let line = String(raw)
            // Strip leading `#` or `//` plus optional whitespace, look for
            // `sentinel:` prefix.
            var trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("#")  { trimmed = String(trimmed.dropFirst()) }
            if trimmed.hasPrefix("//") { trimmed = String(trimmed.dropFirst(2)) }
            trimmed = trimmed.trimmingCharacters(in: .whitespaces)
            guard trimmed.lowercased().hasPrefix("sentinel:") else { continue }
            let after = trimmed.dropFirst("sentinel:".count)
                .trimmingCharacters(in: .whitespaces)
            // Parse key="value" pairs separated by commas (or just key=value).
            // Simple parser: walk char-by-char tracking quotes.
            for (k, v) in keyValuePairs(in: after) {
                dict[k.lowercased()] = v
            }
        }
        return dict
    }

    private static func keyValuePairs(in s: String) -> [(String, String)] {
        var out: [(String, String)] = []
        var i = s.startIndex
        while i < s.endIndex {
            // Skip whitespace + commas
            while i < s.endIndex, s[i].isWhitespace || s[i] == "," { i = s.index(after: i) }
            if i >= s.endIndex { break }
            // Read key until '=' or whitespace
            var key = ""
            while i < s.endIndex, s[i] != "=", !s[i].isWhitespace, s[i] != "," {
                key.append(s[i])
                i = s.index(after: i)
            }
            // Skip optional spaces, expect '='
            while i < s.endIndex, s[i].isWhitespace { i = s.index(after: i) }
            if i < s.endIndex, s[i] == "=" { i = s.index(after: i) }
            while i < s.endIndex, s[i].isWhitespace { i = s.index(after: i) }
            // Read value: quoted or bareword
            var val = ""
            if i < s.endIndex, s[i] == "\"" {
                i = s.index(after: i)
                while i < s.endIndex, s[i] != "\"" {
                    val.append(s[i])
                    i = s.index(after: i)
                }
                if i < s.endIndex { i = s.index(after: i) }
            } else {
                while i < s.endIndex, !s[i].isWhitespace, s[i] != "," {
                    val.append(s[i])
                    i = s.index(after: i)
                }
            }
            if !key.isEmpty { out.append((key, val)) }
        }
        return out
    }
}
