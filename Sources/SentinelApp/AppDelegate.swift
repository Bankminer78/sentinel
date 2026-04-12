// AppDelegate.swift — menu bar status item, window lifecycle, world recorder.
//
// This is the only AppKit code in the project. Everything inside the
// window is SwiftUI hosted in an NSHostingController.

import AppKit
import SwiftUI
import SentinelCore

final class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem?
    var window: NSWindow?
    var recorder: WorldRecorder?
    let state = AppState()

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Menu bar accessory — no Dock icon.
        NSApp.setActivationPolicy(.accessory)

        // Build the main menu so Cmd+C/V/X/A reach focused text fields
        // inside the WKWebView/SwiftUI window. macOS routes shortcuts
        // through NSApp.mainMenu; without it the keyboard does nothing.
        buildMainMenu()

        // Status bar 🛡 icon. Left click = toggle window. Right click = menu.
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem?.button {
            button.title = "🛡"
            button.target = self
            button.action = #selector(statusBarClick)
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }

        // Start the world recorder. It's the daemon-style component that
        // appends a row to the world table every couple of seconds.
        do {
            let db = try Database.shared()
            recorder = WorldRecorder(db: db, intervalS: 2.0)
            recorder?.start()
        } catch {
            NSLog("[Sentinel] failed to start recorder: \(error)")
        }

        // Open the window once at launch so the user sees something.
        DispatchQueue.main.async { [weak self] in
            self?.openWindow()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        recorder?.stop()
    }

    /// Re-opens the dashboard when the user clicks Sentinel.app while
    /// it's already running but has no visible window.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { openWindow() }
        return true
    }

    // MARK: - Status bar click handling

    @objc func statusBarClick() {
        guard let event = NSApp.currentEvent else {
            toggleWindow()
            return
        }
        if event.type == .rightMouseUp || event.modifierFlags.contains(.control) {
            showStatusMenu()
        } else {
            toggleWindow()
        }
    }

    func toggleWindow() {
        if let w = window, w.isVisible {
            w.orderOut(nil)
        } else {
            openWindow()
        }
    }

    func openWindow() {
        if window == nil {
            let content = ContentView().environmentObject(state)
            let hosting = NSHostingController(rootView: content)
            let w = NSWindow(contentViewController: hosting)
            w.title = "Sentinel"
            w.setContentSize(NSSize(width: 900, height: 600))
            w.styleMask = [.titled, .closable, .resizable, .miniaturizable]
            w.isReleasedWhenClosed = false
            w.center()
            window = w
        }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func openWindowAction() { openWindow() }

    func showStatusMenu() {
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Sentinel",
                                action: #selector(openWindowAction),
                                keyEquivalent: "o"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit Sentinel",
                                action: #selector(NSApplication.terminate(_:)),
                                keyEquivalent: "q"))
        // Attach, show, then detach so the next left-click goes back to
        // toggling the window instead of re-showing the menu.
        statusItem?.menu = menu
        statusItem?.button?.performClick(nil)
        statusItem?.menu = nil
    }

    // MARK: - Main menu (Edit / Window / app menu)

    /// macOS routes Cmd+C / Cmd+V / Cmd+X / Cmd+A through NSApp.mainMenu's
    /// Edit menu. Without this, accessory apps have no working clipboard
    /// shortcuts in any text field.
    func buildMainMenu() {
        let main = NSMenu()

        let appItem = NSMenuItem()
        main.addItem(appItem)
        let appMenu = NSMenu()
        appMenu.addItem(NSMenuItem(
            title: "Quit Sentinel",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"))
        appItem.submenu = appMenu

        let editItem = NSMenuItem()
        main.addItem(editItem)
        let edit = NSMenu(title: "Edit")
        edit.addItem(NSMenuItem(title: "Undo",
                                action: Selector(("undo:")),
                                keyEquivalent: "z"))
        edit.addItem(NSMenuItem(title: "Redo",
                                action: Selector(("redo:")),
                                keyEquivalent: "Z"))
        edit.addItem(NSMenuItem.separator())
        edit.addItem(NSMenuItem(title: "Cut",
                                action: #selector(NSText.cut(_:)),
                                keyEquivalent: "x"))
        edit.addItem(NSMenuItem(title: "Copy",
                                action: #selector(NSText.copy(_:)),
                                keyEquivalent: "c"))
        edit.addItem(NSMenuItem(title: "Paste",
                                action: #selector(NSText.paste(_:)),
                                keyEquivalent: "v"))
        edit.addItem(NSMenuItem(title: "Select All",
                                action: #selector(NSText.selectAll(_:)),
                                keyEquivalent: "a"))
        editItem.submenu = edit

        let winItem = NSMenuItem()
        main.addItem(winItem)
        let winMenu = NSMenu(title: "Window")
        winMenu.addItem(NSMenuItem(title: "Close",
                                   action: #selector(NSWindow.performClose(_:)),
                                   keyEquivalent: "w"))
        winItem.submenu = winMenu

        NSApp.mainMenu = main
    }
}
