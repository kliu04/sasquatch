// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "LiDARCapture",
    platforms: [.iOS(.v15)],
    products: [
        .library(name: "LiDARCapture", targets: ["LiDARCapture"]),
    ],
    targets: [
        .target(name: "LiDARCapture"),
    ]
)
