// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Sentinel",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "SentinelApp", targets: ["SentinelApp"]),
        .executable(name: "sentinel", targets: ["sentinel"]),
        .library(name: "SentinelCore", targets: ["SentinelCore"]),
    ],
    targets: [
        // Shared library: DB connection wrapper, schema, models. Used by
        // both the GUI app and the CLI so they speak the same database.
        .target(
            name: "SentinelCore",
            path: "Sources/SentinelCore",
            linkerSettings: [
                .linkedLibrary("sqlite3"),
            ]
        ),

        // Single-file CLI binary. Verbs: check, log, status, commit,
        // committed, kv, pause, resume, emergency-exit, world, running.
        .executableTarget(
            name: "sentinel",
            dependencies: ["SentinelCore"],
            path: "Sources/sentinel"
        ),

        // SwiftUI menu-bar GUI app. Spawns scripts as subprocesses,
        // runs the world recorder, talks to Claude.
        .executableTarget(
            name: "SentinelApp",
            dependencies: ["SentinelCore"],
            path: "Sources/SentinelApp"
        ),
    ]
)
