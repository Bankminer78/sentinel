// ClaudeAPI.swift — talks to Claude via either:
//
//   1. The user's installed `claude` CLI (Claude Code), authenticated
//      via the user's existing OAuth session. No API key needed. This
//      is the preferred path because it uses the user's subscription
//      and doesn't require them to manage a key.
//
//   2. Direct URLSession to api.anthropic.com with an API key from
//      $ANTHROPIC_API_KEY or ~/.config/sentinel/api_key. Fallback only.
//
// In both modes the public surface is the same: `stream(history:
// systemPrompt:resumeSession:)` returns an AsyncStream of events that
// the chat view consumes.
//
// The CLI path can ALSO emit a `.sessionStarted(id)` event so the chat
// view can pass `resumeSession: id` on the next turn for proper
// multi-turn continuity.

import Foundation

enum ClaudeAuth {
    case cli(URL)               // path to the claude binary
    case apiKey(String)
    case none

    static func detect() -> ClaudeAuth {
        if let url = findClaudeCLI() {
            return .cli(url)
        }
        if let key = loadAPIKey() {
            return .apiKey(key)
        }
        return .none
    }

    /// True if Claude is reachable right now without further setup.
    /// For .cli we don't actually probe — we trust the binary exists.
    /// For .apiKey we trust the env var. The chat surface will surface
    /// real errors if either is wrong.
    var isReady: Bool {
        switch self {
        case .none: return false
        default: return true
        }
    }

    var displayName: String {
        switch self {
        case .cli: return "Claude CLI (OAuth)"
        case .apiKey: return "API key"
        case .none: return "not configured"
        }
    }
}

private func findClaudeCLI() -> URL? {
    let fm = FileManager.default
    let candidates = [
        "\(NSHomeDirectory())/.local/bin/claude",
        "\(NSHomeDirectory())/.claude/local/claude",
        "/usr/local/bin/claude",
        "/opt/homebrew/bin/claude",
    ]
    for path in candidates {
        if fm.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
    }
    // Walk PATH from the user's login shell environment.
    if let pathEnv = ProcessInfo.processInfo.environment["PATH"] {
        for dir in pathEnv.split(separator: ":") {
            let p = "\(dir)/claude"
            if fm.isExecutableFile(atPath: p) {
                return URL(fileURLWithPath: p)
            }
        }
    }
    return nil
}

private func loadAPIKey() -> String? {
    if let env = ProcessInfo.processInfo.environment["ANTHROPIC_API_KEY"],
       !env.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        return env.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    let url = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent(".config/sentinel/api_key")
    if let s = try? String(contentsOf: url, encoding: .utf8) {
        let trimmed = s.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmed.isEmpty { return trimmed }
    }
    return nil
}

enum ClaudeStreamEvent {
    case textDelta(String)
    case stop
    case error(String)
    /// CLI mode only: emitted on the first init event so the chat view
    /// can pass `resumeSession: id` on subsequent turns.
    case sessionStarted(String)
}

struct ClaudeMessage {
    let role: String      // "user" or "assistant"
    let content: String
}

final class ClaudeAPI {
    let auth: ClaudeAuth

    init(auth: ClaudeAuth) {
        self.auth = auth
    }

    /// Returns a one-shot login command the user can run in Terminal.app
    /// to authenticate the Claude CLI. Used by ChatView's "Log in" button.
    static func loginCommand() -> String {
        // The Claude CLI's /login slash command opens an interactive
        // browser-based OAuth flow. Running `claude` with no args drops
        // into an interactive REPL where the user types `/login`.
        // Spawning that in Terminal.app is the simplest reliable path.
        if let url = findClaudeCLI() {
            return "\(url.path) /login"
        }
        return "claude /login"
    }

    /// Top-level dispatch. Routes to the right backend based on `auth`.
    func stream(history: [ClaudeMessage],
                systemPrompt: String,
                resumeSession: String?) -> AsyncStream<ClaudeStreamEvent> {
        switch auth {
        case .cli(let bin):
            return streamViaCLI(bin: bin,
                                history: history,
                                systemPrompt: systemPrompt,
                                resumeSession: resumeSession)
        case .apiKey(let key):
            return streamViaAPIKey(key: key,
                                   history: history,
                                   systemPrompt: systemPrompt)
        case .none:
            return AsyncStream { continuation in
                continuation.yield(.error("Claude is not configured. Click Log in or set ANTHROPIC_API_KEY."))
                continuation.finish()
            }
        }
    }

    // MARK: - CLI backend

    private func streamViaCLI(bin: URL,
                              history: [ClaudeMessage],
                              systemPrompt: String,
                              resumeSession: String?) -> AsyncStream<ClaudeStreamEvent> {
        AsyncStream { continuation in
            let task = Task.detached {
                let proc = Process()
                proc.executableURL = bin

                // Last user message is the prompt for this turn. The
                // earlier turns come from --resume's session history;
                // for the first turn we just send the user message.
                let prompt = history.last?.content ?? ""

                var args: [String] = [
                    "-p", prompt,
                    "--append-system-prompt", systemPrompt,
                    "--output-format", "stream-json",
                    "--include-partial-messages",
                    "--verbose",
                    // Strip ALL tools so Claude can only emit text.
                    // We want it to write the lock as a code block in
                    // the response, not actually create files itself.
                    "--disallowedTools",
                    "Bash Edit Read Glob Grep WebFetch WebSearch Write Task TodoWrite NotebookEdit BashOutput KillShell",
                ]
                if let id = resumeSession {
                    args.append("--resume")
                    args.append(id)
                }
                proc.arguments = args

                // Run from a clean throwaway cwd so claude doesn't pick
                // up nearby CLAUDE.md / .claude/ from random directories.
                let tmp = FileManager.default.temporaryDirectory
                    .appendingPathComponent("sentinel-chat", isDirectory: true)
                try? FileManager.default.createDirectory(
                    at: tmp, withIntermediateDirectories: true)
                proc.currentDirectoryURL = tmp

                let outPipe = Pipe()
                let errPipe = Pipe()
                proc.standardOutput = outPipe
                proc.standardError = errPipe

                let bufferLock = NSLock()
                var lineBuffer = ""

                outPipe.fileHandleForReading.readabilityHandler = { handle in
                    let data = handle.availableData
                    guard !data.isEmpty,
                          let chunk = String(data: data, encoding: .utf8) else { return }
                    bufferLock.lock()
                    lineBuffer += chunk
                    var lines: [String] = []
                    while let nl = lineBuffer.firstIndex(of: "\n") {
                        lines.append(String(lineBuffer[..<nl]))
                        lineBuffer = String(lineBuffer[lineBuffer.index(after: nl)...])
                    }
                    bufferLock.unlock()
                    for line in lines {
                        if line.isEmpty { continue }
                        if let json = parseJSON(line) {
                            handleCLIEvent(json: json,
                                           continuation: continuation)
                        }
                    }
                }

                proc.terminationHandler = { _ in
                    outPipe.fileHandleForReading.readabilityHandler = nil
                    errPipe.fileHandleForReading.readabilityHandler = nil
                    // Drain any remaining stderr for the user
                    let errData = errPipe.fileHandleForReading.availableData
                    if !errData.isEmpty,
                       let s = String(data: errData, encoding: .utf8),
                       !s.trimmingCharacters(in: .whitespaces).isEmpty {
                        continuation.yield(.error(s))
                    }
                    continuation.finish()
                }

                do {
                    try proc.run()
                } catch {
                    continuation.yield(.error("failed to launch claude: \(error)"))
                    continuation.finish()
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    // MARK: - API key backend (fallback)

    private func streamViaAPIKey(key: String,
                                 history: [ClaudeMessage],
                                 systemPrompt: String) -> AsyncStream<ClaudeStreamEvent> {
        AsyncStream { continuation in
            let task = Task {
                do {
                    var req = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
                    req.httpMethod = "POST"
                    req.timeoutInterval = 60
                    req.setValue(key, forHTTPHeaderField: "x-api-key")
                    req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
                    req.setValue("application/json", forHTTPHeaderField: "content-type")
                    let body: [String: Any] = [
                        "model": "claude-sonnet-4-5",
                        "max_tokens": 4096,
                        "system": systemPrompt,
                        "messages": history.map { ["role": $0.role, "content": $0.content] },
                        "stream": true,
                    ]
                    req.httpBody = try JSONSerialization.data(withJSONObject: body)
                    let (bytes, response) = try await URLSession.shared.bytes(for: req)
                    if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                        var errBody = ""
                        for try await line in bytes.lines {
                            errBody += line + "\n"
                            if errBody.count > 2000 { break }
                        }
                        continuation.yield(.error("HTTP \(http.statusCode): \(errBody.prefix(500))"))
                        continuation.finish()
                        return
                    }
                    for try await line in bytes.lines {
                        if Task.isCancelled { break }
                        guard line.hasPrefix("data:") else { continue }
                        let payload = String(line.dropFirst(5))
                            .trimmingCharacters(in: .whitespaces)
                        if payload.isEmpty || payload == "[DONE]" { continue }
                        guard let json = parseJSON(payload) else { continue }
                        let type = json["type"] as? String ?? ""
                        switch type {
                        case "content_block_delta":
                            if let delta = json["delta"] as? [String: Any],
                               let text = delta["text"] as? String {
                                continuation.yield(.textDelta(text))
                            }
                        case "message_stop":
                            continuation.yield(.stop)
                            continuation.finish()
                            return
                        case "error":
                            let msg = (json["error"] as? [String: Any])?["message"] as? String
                                      ?? "(unknown error)"
                            continuation.yield(.error(msg))
                            continuation.finish()
                            return
                        default:
                            break
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.yield(.error(String(describing: error)))
                    continuation.finish()
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}

// MARK: - Free helpers

private func parseJSON(_ s: String) -> [String: Any]? {
    guard let data = s.data(using: .utf8) else { return nil }
    return (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
}

/// Pull a `content_block_delta`-shaped text out of the CLI's nested
/// `stream_event` envelope. Schema observed in claude-cli 2.x:
///
///     {"type":"system","subtype":"init","session_id":"..."}
///     {"type":"stream_event",
///      "event":{"type":"content_block_delta",
///               "index":0,
///               "delta":{"type":"text_delta","text":"hello"}}}
///     {"type":"stream_event","event":{"type":"message_stop"}}
///     {"type":"result","subtype":"success",...}
private func handleCLIEvent(json: [String: Any],
                            continuation: AsyncStream<ClaudeStreamEvent>.Continuation) {
    let type = json["type"] as? String ?? ""
    switch type {
    case "system":
        if json["subtype"] as? String == "init",
           let sid = json["session_id"] as? String {
            continuation.yield(.sessionStarted(sid))
        }
    case "stream_event":
        guard let event = json["event"] as? [String: Any] else { return }
        let etype = event["type"] as? String ?? ""
        switch etype {
        case "content_block_delta":
            if let delta = event["delta"] as? [String: Any],
               (delta["type"] as? String == "text_delta"),
               let text = delta["text"] as? String {
                continuation.yield(.textDelta(text))
            }
        case "message_stop":
            continuation.yield(.stop)
        default:
            break
        }
    case "result":
        if let isError = json["is_error"] as? Bool, isError {
            let msg = json["error"] as? String
                ?? json["result"] as? String
                ?? "claude returned an error"
            continuation.yield(.error(msg))
        }
    default:
        break
    }
}
