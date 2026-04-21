// ChatView.swift — native SwiftUI chat with Claude streaming + lock
// extraction + approve-to-disk.
//
// Format we expect Claude to emit (taught via the system prompt):
//
//     lock: hello.sh
//     A short explanation paragraph.
//
//     ```bash
//     #!/usr/bin/env bash
//     # sentinel: name="Hello"
//     ...
//     ```
//
// We parse the `lock: <filename>` line and the first fenced code block
// out of each assistant turn. If both are present, a "Review and install"
// pane appears at the bottom of the chat with the script source and an
// Approve button. Clicking Approve writes the file to the locks dir and
// the AppDelegate's refresh timer surfaces it in the sidebar within ~1.5s.

import SwiftUI

struct ChatView: View {
    @EnvironmentObject var state: AppState

    @State private var messages: [ChatTurn] = []
    @State private var streamingText: String = ""
    @State private var isStreaming: Bool = false
    @State private var inputText: String = ""
    @State private var staged: StagedLock? = nil
    @State private var auth: ClaudeAuth = ClaudeAuth.detect()
    @State private var sessionID: String? = nil
    @State private var errorBanner: String? = nil

    var body: some View {
        VStack(spacing: 0) {
            authBanner
            if let err = errorBanner {
                ErrorBanner(text: err) { errorBanner = nil }
            }
            messageList
            if let staged = staged {
                ReviewPane(staged: staged,
                           onApprove: { approve(staged) },
                           onReject:  { self.staged = nil })
            }
            inputBar
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    @ViewBuilder
    private var authBanner: some View {
        switch auth {
        case .none:
            AuthSetupBanner(onLogin: { startLogin() },
                            onRefresh: { auth = ClaudeAuth.detect() })
        case .cli:
            EmptyView()  // happy path; no banner
        case .apiKey:
            EmptyView()
        }
    }

    private func startLogin() {
        // Spawn Terminal.app with `claude /login`. The Claude CLI handles
        // the OAuth dance via the user's browser. After completion, the
        // user comes back to Sentinel and clicks Refresh on the banner.
        let cmd = ClaudeAPI.loginCommand()
        let escaped = cmd.replacingOccurrences(of: "\"", with: "\\\"")
        let script = "tell application \"Terminal\" to do script \"\(escaped)\""
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
        proc.arguments = ["-e", script]
        do {
            try proc.run()
        } catch {
            errorBanner = "couldn't open Terminal.app: \(error)"
        }
    }

    // MARK: - Subviews

    private var messageList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 16) {
                    if messages.isEmpty && streamingText.isEmpty {
                        intro
                            .padding(.top, 40)
                    }
                    ForEach(messages) { turn in
                        MessageBubble(turn: turn)
                            .id(turn.id)
                    }
                    if !streamingText.isEmpty || isStreaming {
                        MessageBubble(turn: ChatTurn(
                            role: .assistant,
                            content: streamingText.isEmpty ? "…" : streamingText))
                            .id("streaming")
                    }
                }
                .padding()
            }
            .background(Color(nsColor: .textBackgroundColor))
            .onChange(of: streamingText) { _ in
                proxy.scrollTo("streaming", anchor: .bottom)
            }
            .onChange(of: messages.count) { _ in
                if let last = messages.last {
                    proxy.scrollTo(last.id, anchor: .bottom)
                }
            }
        }
    }

    private var intro: some View {
        VStack(spacing: 8) {
            Image(systemName: "wand.and.stars")
                .font(.system(size: 36))
                .foregroundStyle(.tint)
            Text("Author a lock")
                .font(.title3).bold()
            Text("Describe what you want — Claude will write a script and you can review it before installing.")
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 460)
            VStack(alignment: .leading, spacing: 4) {
                Text("Examples:")
                    .font(.caption.bold())
                    .foregroundStyle(.secondary)
                Text("• Block YouTube weekday mornings 9-noon")
                Text("• Lock me to TextEdit and Wikipedia French Revolution for 2 minutes")
                Text("• 25/5 pomodoro that notifies me at each cycle")
            }
            .font(.caption)
            .foregroundStyle(.secondary)
            .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
    }

    private var inputBar: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(alignment: .bottom, spacing: 8) {
                TextField("Describe a lock…",
                          text: $inputText,
                          axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(1...6)
                    .disabled(isStreaming)
                    .onSubmit { send() }

                Button {
                    send()
                } label: {
                    if isStreaming {
                        ProgressView().controlSize(.small)
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 22))
                    }
                }
                .buttonStyle(.plain)
                .disabled(inputText.isEmpty || isStreaming || !auth.isReady)
            }
            .padding(12)
        }
    }

    // MARK: - Actions

    private func send() {
        let prompt = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !prompt.isEmpty, auth.isReady, !isStreaming else { return }
        inputText = ""
        staged = nil
        errorBanner = nil
        let userTurn = ChatTurn(role: .user, content: prompt)
        messages.append(userTurn)
        streamingText = ""
        isStreaming = true

        let resume = sessionID
        let snapshot = messages

        Task {
            let api = ClaudeAPI(auth: auth)
            let history = snapshot.map {
                ClaudeMessage(role: $0.role.wireValue, content: $0.content)
            }
            for await event in api.stream(history: history,
                                          systemPrompt: ChatView.systemPrompt,
                                          resumeSession: resume) {
                switch event {
                case .textDelta(let text):
                    await MainActor.run { streamingText += text }
                case .stop:
                    await MainActor.run { finalizeAssistantTurn() }
                case .error(let msg):
                    await MainActor.run {
                        errorBanner = msg
                        isStreaming = false
                        streamingText = ""
                    }
                case .sessionStarted(let id):
                    await MainActor.run { sessionID = id }
                }
            }
        }
    }

    private func finalizeAssistantTurn() {
        let text = streamingText
        streamingText = ""
        isStreaming = false
        guard !text.isEmpty else { return }
        messages.append(ChatTurn(role: .assistant, content: text))
        if let stagedLock = StagedLock.from(text: text) {
            staged = stagedLock
        }
    }

    private func approve(_ staged: StagedLock) {
        do {
            LockStore.ensureDirExists()
            let target = LockStore.locksDir.appendingPathComponent(staged.filename)
            // Don't clobber existing files silently
            if FileManager.default.fileExists(atPath: target.path) {
                let backup = LockStore.locksDir.appendingPathComponent(
                    "\(staged.filename).bak.\(Int(Date().timeIntervalSince1970))")
                try FileManager.default.moveItem(at: target, to: backup)
            }
            try staged.body.write(to: target, atomically: true, encoding: .utf8)
            // chmod +x only for files that are actual lock scripts — HTML
            // dashboards and future asset files (CSS, JSON) don't need it.
            let ext = (staged.filename as NSString).pathExtension.lowercased()
            let scriptExts: Set<String> = ["sh", "bash", "py", "python",
                                           "swift", "rb", "ruby", "js", "mjs"]
            if scriptExts.contains(ext) {
                try FileManager.default.setAttributes(
                    [.posixPermissions: 0o755], ofItemAtPath: target.path)
            }
            // Refresh + jump to the corresponding lock. For a script:
            // `foo.sh` → route to lock "foo". For a dashboard: `foo.html`
            // → also route to lock "foo" (so the user sees the Dashboard
            // tab render with the new HTML immediately).
            state.locks = LockStore.listLocks()
            self.staged = nil
            let basename = (staged.filename as NSString).deletingPathExtension
            let verb = ext == "html" ? "Installed dashboard" : "Installed"
            messages.append(ChatTurn(role: .system,
                                     content: "\(verb) `\(staged.filename)`."))
            if state.locks.contains(where: { $0.name == basename }) {
                state.route = .lock(basename)
            }
        } catch {
            errorBanner = "Failed to install: \(error)"
        }
    }

    // MARK: - System prompt

    static let systemPrompt = """
    You are a Sentinel lock author. The user describes what they want; you reply with one script that does it.

    A "lock" is a single executable script (bash, python, or swift). The user reviews your file before it's installed.

    The Sentinel daemon ships a `sentinel` CLI on PATH that scripts call for cross-lock features:

      sentinel check "$NAME" || exit 0     heartbeat + global pause + per-lock stop check.
                                            Put this at the top of every loop iteration.
      sentinel log <source> <event> [json]  append a row to the audit log
      sentinel status <name> <text>        update the sidebar display string for a lock
      sentinel commit <kind> <target> <secs>  create a write-once commitment (passive flag)
      sentinel committed <kind> <target>   exit 0 if a matching commitment is active
      sentinel kv get|set|del <key> [val]  cross-lock blackboard
      sentinel pause / sentinel resume     toggle the global pause flag
      sentinel emergency-exit <reason>     release all commitments + pause + log
      sentinel world                       latest window snapshot as JSON
      sentinel running                     JSON list of running locks

    Environment:
      $SENTINEL_LOCK_NAME — pre-set to the lock's name (use this with `sentinel check`)

    Native macOS commands you can use directly (no abstractions, no permission ceremony):
      osascript -e '...'                   run AppleScript
      open -a "TextEdit"                   launch / activate an app
      pmset, networksetup, etc.            other macOS CLIs

    ===== RESTART-SAFETY RULE — STRICT =====

    The user's invariant: **a force-restart of the Mac must end ALL enforcement**.
    Nothing the script writes may keep enforcing after the script process dies.
    The script IS the enforcement loop — when the script exits (normally, via
    SIGTERM, or via a force-restart killing the process), enforcement must stop.

    FORBIDDEN — these survive after the script dies and break the rule:

    - Writing to /etc/hosts (entries persist across restart and across script exit)
    - Installing LaunchAgents (~/Library/LaunchAgents/, /Library/LaunchAgents/,
      /Library/LaunchDaemons/) — these auto-relaunch the script at next login
    - Modifying /etc/sudoers or /etc/sudoers.d/
    - Adding crontab entries (`crontab -e`, `/etc/cron*`, `launchctl bootstrap`)
    - Writing files anywhere outside ~/Library/Application Support/Sentinel/
    - Calling `sudo` for anything except read-only checks
    - `pmset`, `nvram`, `csrutil`, `tmutil`, `defaults write` on system domains
    - Installing global software (`brew install`, `npm i -g`, `pip install --user`)

    ALLOWED — these are tied to the script's lifetime:

    - Polling foreground app via osascript / NSWorkspace and redirecting via
      `open -a TextEdit` when the user strays
    - Spawning your own NSWindow / fullscreen overlay (the window dies with the
      process; force-restart kills both)
    - Showing macOS notifications via `osascript -e 'display notification ...'`
    - Reading `sentinel world` to see what's on the screen
    - Calling `sentinel commit` — commitments are PASSIVE flags other scripts
      check; they don't actively enforce anything by themselves
    - Reading/writing files inside ~/Library/Application Support/Sentinel/ via
      the sentinel CLI (kv, log, status)

    The general principle: **when your script's process dies, nothing should
    still be running on the user's behalf.** If your enforcement strategy
    requires installing a system file, you're solving it wrong — use a poll
    loop instead.

    FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

    lock: <filename.ext>
    A 1-2 sentence explanation of what the script does.

    ```bash
    #!/usr/bin/env bash
    # sentinel: name="Display name shown in the sidebar"
    # sentinel: description="What this lock does"
    # ...rest of script...
    ```

    The first line MUST be exactly `lock: <filename.ext>` with a sensible filename like
    `youtube_or_textedit.sh` or `pomodoro.py`. The filename's extension chooses the
    interpreter (.sh → bash, .py → python3, .swift → swift, .rb → ruby, .js → node).

    Keep scripts short — 20-60 lines is normal. No abstractions, no helper modules.
    Use real OS commands directly.

    ==================================================================
    OPTIONAL DASHBOARD (second turn, when the user asks)
    ==================================================================

    Each lock can ship a SwiftUI-free, Claude-authored **Dashboard tab**:
    a `<lockname>.html` file placed next to the script. If present, the
    Sentinel app loads it in a WKWebView and uses it as the default tab
    for that lock (in place of the generic status card).

    Only author a dashboard when the user asks for one. Emit it the same
    way as a script — `lock: <lockname>.html` followed by ONE fenced
    HTML code block.

    The page runs in a webview with an injected `window.sentinel` bridge.
    All methods return Promises:

      sentinel.kv.get(key)             → string value or null
      sentinel.kv.set(key, val)        → true
      sentinel.kv.del(key)             → true
      sentinel.running(name?)          → {pid, startedAt, lastHeartbeat, statusText}
                                          or null if not running. `name` defaults
                                          to this dashboard's own lock.
      sentinel.logs(name?, limit?)     → array of {id, ts, source, event, payload}
                                          sorted newest first.
      sentinel.run(name?)              → true. Spawns the lock.
      sentinel.stop(name?)             → true. SIGTERMs the lock.
      sentinel.commit(kind, target, secs) → true. Write-once commitment.
      sentinel.committed(kind, target?) → bool.
      sentinel.world()                 → {ts, windows:[{app,title,...}],
                                          foregroundApp, foregroundWindow}

    `window.sentinel.lockName` is a string with the lock's basename so
    you don't have to hardcode it.

    STYLING: use `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui`
    fonts and `color-scheme: light dark` + media queries so the dashboard
    matches the user's macOS appearance. Use `tabular-nums` for any
    time/number displays. Keep backgrounds `transparent` so the app's
    window chrome shows through.

    DYNAMIC: poll with `setInterval(refresh, 1000)` and call whichever
    sentinel.* methods you need. Don't over-render — only update DOM
    elements when values change.

    Example shape (trimmed):
    ```html
    <!doctype html>
    <style>
      body { font-family: -apple-system, sans-serif; background: transparent; }
      .time { font-size: 48px; font-variant-numeric: tabular-nums; }
    </style>
    <div class="time" id="time">—</div>
    <script>
      async function tick() {
        const used = parseInt(await sentinel.kv.get("quota:...:used_s")) || 0;
        document.getElementById("time").textContent = used + "s";
      }
      tick(); setInterval(tick, 1000);
    </script>
    ```
    """
}

// MARK: - Models / subviews

struct ChatTurn: Identifiable {
    let id = UUID()
    let role: Role
    let content: String

    enum Role {
        case user, assistant, system
        var wireValue: String {
            switch self {
            case .user: return "user"
            case .assistant: return "assistant"
            case .system: return "user"
            }
        }
    }
}

private struct MessageBubble: View {
    let turn: ChatTurn

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            if turn.role == .user { Spacer() }
            VStack(alignment: turn.role == .user ? .trailing : .leading, spacing: 2) {
                Text(label)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text(turn.content)
                    .textSelection(.enabled)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(background)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .foregroundStyle(turn.role == .user ? Color.white : Color.primary)
                    .frame(maxWidth: 600, alignment: turn.role == .user ? .trailing : .leading)
            }
            if turn.role != .user { Spacer() }
        }
    }

    private var label: String {
        switch turn.role {
        case .user: return "you"
        case .assistant: return "claude"
        case .system: return "sentinel"
        }
    }

    private var background: Color {
        switch turn.role {
        case .user: return Color.accentColor
        case .assistant: return Color(nsColor: .windowBackgroundColor)
        case .system: return Color.green.opacity(0.15)
        }
    }
}

struct StagedLock: Equatable {
    let filename: String
    let body: String

    /// Parse `lock: <filename>` + first fenced code block out of an
    /// assistant turn. Returns nil if either is missing.
    static func from(text: String) -> StagedLock? {
        // 1. Find the filename header. Match the FIRST line that begins
        // with "lock: ".
        var filename: String? = nil
        for raw in text.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.lowercased().hasPrefix("lock:") {
                let after = line.dropFirst("lock:".count)
                    .trimmingCharacters(in: .whitespaces)
                if !after.isEmpty {
                    // Sanitize: only allow [a-zA-Z0-9._-]
                    let sanitized = after.unicodeScalars.map { scalar -> Character in
                        let ok = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "._-"))
                        return ok.contains(scalar) ? Character(scalar) : "_"
                    }
                    filename = String(sanitized)
                    break
                }
            }
        }
        guard let filename = filename else { return nil }

        // 2. Find the first fenced code block. The fence is ``` optionally
        // followed by a language tag.
        guard let codeStart = text.range(of: "```") else { return nil }
        // Skip past the language tag (the rest of the opening fence line)
        let afterFence = text[codeStart.upperBound...]
        guard let newlineAfterFence = afterFence.firstIndex(of: "\n") else { return nil }
        let bodyStart = afterFence.index(after: newlineAfterFence)
        // Find closing fence
        guard let codeEnd = text.range(of: "```", range: bodyStart..<text.endIndex) else { return nil }
        let body = String(text[bodyStart..<codeEnd.lowerBound])
        return StagedLock(filename: filename, body: body)
    }
}

private struct ReviewPane: View {
    let staged: StagedLock
    let onApprove: () -> Void
    let onReject: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
            HStack {
                Image(systemName: "doc.badge.plus")
                Text("Review and install: ")
                + Text(staged.filename).bold().font(.system(.body, design: .monospaced))
                Spacer()
                Button("Reject", role: .destructive, action: onReject)
                Button("Approve and install", action: onApprove)
                    .buttonStyle(.borderedProminent)
            }
            ScrollView {
                Text(staged.body)
                    .font(.system(.callout, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding(10)
            }
            .frame(maxHeight: 240)
            .background(Color(nsColor: .textBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .padding(12)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

private struct AuthSetupBanner: View {
    let onLogin: () -> Void
    let onRefresh: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "person.crop.circle.badge.exclamationmark")
                    .font(.title3)
                    .foregroundStyle(.orange)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Not signed in to Claude")
                        .font(.callout).bold()
                    Text("Sentinel uses your existing Claude subscription via the Claude CLI. Click Log in to authenticate (a Terminal window will open), then click Refresh.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            HStack(spacing: 8) {
                Button("Log in to Claude", action: onLogin)
                    .buttonStyle(.borderedProminent)
                Button("Refresh", action: onRefresh)
                    .buttonStyle(.bordered)
                Spacer()
                Text("or set ANTHROPIC_API_KEY")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.orange.opacity(0.12))
    }
}

private struct ErrorBanner: View {
    let text: String
    let onDismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
            Text(text)
                .font(.caption)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
            Button(action: onDismiss) {
                Image(systemName: "xmark")
            }
            .buttonStyle(.plain)
        }
        .padding(10)
        .background(Color.red.opacity(0.12))
    }
}
