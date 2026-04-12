// ClaudeAPI.swift — direct URLSession client for the Anthropic Messages
// API with SSE streaming. No SDK dependency.
//
// The Messages API streaming protocol uses text/event-stream frames where
// each frame is one or more `field: value` lines separated by `\n\n`. We
// only care about `data:` lines; each carries a JSON object with a `type`
// field. We switch on `type`:
//   - content_block_delta → yield .textDelta(delta.text)
//   - message_stop        → yield .stop and finish
//   - everything else     → ignored (message_start, content_block_start,
//                            ping, message_delta, etc.)

import Foundation

enum ClaudeAPIError: Error, CustomStringConvertible {
    case missingAPIKey
    case http(Int, String)
    case transport(String)

    var description: String {
        switch self {
        case .missingAPIKey:
            return "missing ANTHROPIC_API_KEY (env var or ~/.config/sentinel/api_key)"
        case .http(let code, let body):
            return "claude api http \(code): \(body.prefix(400))"
        case .transport(let msg):
            return "claude transport: \(msg)"
        }
    }
}

enum ClaudeStreamEvent {
    case textDelta(String)
    case stop
    case error(String)
}

struct ClaudeMessage {
    let role: String      // "user" or "assistant"
    let content: String
}

final class ClaudeAPI {
    let apiKey: String
    let model: String
    private let endpoint = URL(string: "https://api.anthropic.com/v1/messages")!

    init(apiKey: String, model: String = "claude-sonnet-4-5") {
        self.apiKey = apiKey
        self.model = model
    }

    /// Look for an API key in this order:
    ///   1. env var ANTHROPIC_API_KEY
    ///   2. ~/.config/sentinel/api_key (single line, trimmed)
    static func loadAPIKey() -> String? {
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

    /// Stream a response. Each yielded event is either a text delta or
    /// the terminal `.stop`. The caller appends text deltas to whatever
    /// buffer it's displaying.
    func stream(history: [ClaudeMessage],
                systemPrompt: String) -> AsyncStream<ClaudeStreamEvent> {
        AsyncStream { continuation in
            let task = Task {
                do {
                    var req = URLRequest(url: endpoint)
                    req.httpMethod = "POST"
                    req.timeoutInterval = 60
                    req.setValue(apiKey, forHTTPHeaderField: "x-api-key")
                    req.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
                    req.setValue("application/json", forHTTPHeaderField: "content-type")

                    let body: [String: Any] = [
                        "model": model,
                        "max_tokens": 4096,
                        "system": systemPrompt,
                        "messages": history.map { ["role": $0.role, "content": $0.content] },
                        "stream": true,
                    ]
                    req.httpBody = try JSONSerialization.data(
                        withJSONObject: body, options: [])

                    let (bytes, response) = try await URLSession.shared.bytes(for: req)
                    if let http = response as? HTTPURLResponse, http.statusCode != 200 {
                        // Drain the body for the error message
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
                        guard let data = payload.data(using: .utf8),
                              let json = try? JSONSerialization.jsonObject(with: data)
                                              as? [String: Any] else { continue }
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
                            break // ignored
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
