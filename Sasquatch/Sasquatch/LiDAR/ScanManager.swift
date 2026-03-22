import Foundation
import ARKit
import CoreVideo
import UIKit
import Observation

@Observable
class ScanManager {
    var isExporting = false
    var exportedFiles: [URL] = []
    var hasCaptured = false
    var hasLiDAR = false

    weak var arSession: ARSession?

    private var capturedFrame: ARFrame?

    func checkLiDAR() {
        hasLiDAR = ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
    }

    func capture() {
        guard let frame = arSession?.currentFrame else { return }
        capturedFrame = frame
        exportedFiles = []
        hasCaptured = true
    }

    var hasMeshData: Bool {
        hasCaptured && capturedFrame?.sceneDepth != nil
    }

    func export() {
        guard let frame = capturedFrame else { return }
        isExporting = true

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            do {
                let timestamp = Int(Date().timeIntervalSince1970)
                let docsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]

                var files: [URL] = []

                // Always write PNG from camera
                let pngURL = docsDir.appendingPathComponent("scan_\(timestamp).png")
                try self.writePNG(frame: frame, to: pngURL)
                files.append(pngURL)

                // Write PLY only if LiDAR depth is available
                if frame.sceneDepth != nil {
                    let plyURL = docsDir.appendingPathComponent("scan_\(timestamp).ply")
                    try self.writePLY(frame: frame, to: plyURL)
                    files.insert(plyURL, at: 0)
                }

                DispatchQueue.main.async {
                    self.exportedFiles = files
                    self.isExporting = false
                }
            } catch {
                print("Export failed: \(error)")
                DispatchQueue.main.async {
                    self.isExporting = false
                }
            }
        }
    }

    // MARK: - PLY Writing

    private func writePLY(frame: ARFrame, to url: URL) throws {
        guard let sceneDepth = frame.sceneDepth else {
            throw NSError(domain: "LiDARCapture", code: 1, userInfo: [NSLocalizedDescriptionKey: "No depth data"])
        }

        let depthMap = sceneDepth.depthMap
        let colorBuffer = frame.capturedImage
        let camera = frame.camera
        let intrinsics = camera.intrinsics

        let depthWidth = CVPixelBufferGetWidth(depthMap)
        let depthHeight = CVPixelBufferGetHeight(depthMap)
        let colorWidth = CVPixelBufferGetWidth(colorBuffer)
        let colorHeight = CVPixelBufferGetHeight(colorBuffer)

        let fx = intrinsics[0][0]
        let fy = intrinsics[1][1]
        let cx = intrinsics[2][0]
        let cy = intrinsics[2][1]

        let depthScaleX = Float(depthWidth) / Float(colorWidth)
        let depthScaleY = Float(depthHeight) / Float(colorHeight)

        CVPixelBufferLockBaseAddress(depthMap, .readOnly)
        CVPixelBufferLockBaseAddress(colorBuffer, .readOnly)
        defer {
            CVPixelBufferUnlockBaseAddress(depthMap, .readOnly)
            CVPixelBufferUnlockBaseAddress(colorBuffer, .readOnly)
        }

        guard let depthBase = CVPixelBufferGetBaseAddress(depthMap),
              let yPlane = CVPixelBufferGetBaseAddressOfPlane(colorBuffer, 0),
              let cbcrPlane = CVPixelBufferGetBaseAddressOfPlane(colorBuffer, 1) else {
            throw NSError(domain: "LiDARCapture", code: 2, userInfo: [NSLocalizedDescriptionKey: "Cannot access buffers"])
        }

        let depthBytesPerRow = CVPixelBufferGetBytesPerRow(depthMap)
        let yStride = CVPixelBufferGetBytesPerRowOfPlane(colorBuffer, 0)
        let cbcrStride = CVPixelBufferGetBytesPerRowOfPlane(colorBuffer, 1)

        let cameraTransform = camera.transform

        var vertices: [(x: Float, y: Float, z: Float, r: UInt8, g: UInt8, b: UInt8)] = []
        vertices.reserveCapacity(colorWidth * colorHeight)

        for row in 0..<colorHeight {
            for col in 0..<colorWidth {
                let depthX = Float(col) * depthScaleX
                let depthY = Float(row) * depthScaleY

                let depth = sampleDepth(
                    depthBase: depthBase, bytesPerRow: depthBytesPerRow,
                    width: depthWidth, height: depthHeight,
                    x: depthX, y: depthY
                )

                guard depth > 0 && depth < 10.0 else { continue }

                let xCam = (Float(col) - cx) * depth / fx
                let yCam = (Float(row) - cy) * depth / fy
                let zCam = depth

                let camPoint = SIMD4<Float>(xCam, yCam, zCam, 1.0)
                let worldPoint = cameraTransform * camPoint

                let (r, g, b) = sampleYCbCr(
                    yPlane: yPlane, cbcrPlane: cbcrPlane,
                    yStride: yStride, cbcrStride: cbcrStride,
                    x: col, y: row
                )

                vertices.append((worldPoint.x, worldPoint.y, worldPoint.z, r, g, b))
            }
        }

        var ply = "ply\nformat ascii 1.0\n"
        ply += "element vertex \(vertices.count)\n"
        ply += "property float x\n"
        ply += "property float y\n"
        ply += "property float z\n"
        ply += "property uchar red\n"
        ply += "property uchar green\n"
        ply += "property uchar blue\n"
        ply += "end_header\n"

        for v in vertices {
            ply += "\(v.x) \(v.y) \(v.z) \(v.r) \(v.g) \(v.b)\n"
        }

        try ply.write(to: url, atomically: true, encoding: .utf8)
    }

    // MARK: - PNG Writing

    private func writePNG(frame: ARFrame, to url: URL) throws {
        let pixelBuffer = frame.capturedImage
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let context = CIContext()
        guard let cgImage = context.createCGImage(ciImage, from: ciImage.extent) else {
            throw NSError(domain: "LiDARCapture", code: 3, userInfo: [NSLocalizedDescriptionKey: "Failed to create image"])
        }
        let uiImage = UIImage(cgImage: cgImage, scale: 1.0, orientation: .right)
        guard let pngData = uiImage.pngData() else {
            throw NSError(domain: "LiDARCapture", code: 4, userInfo: [NSLocalizedDescriptionKey: "Failed to encode PNG"])
        }
        try pngData.write(to: url)
    }

    // MARK: - YCbCr to RGB

    private func sampleYCbCr(
        yPlane: UnsafeMutableRawPointer,
        cbcrPlane: UnsafeMutableRawPointer,
        yStride: Int, cbcrStride: Int,
        x: Int, y: Int
    ) -> (UInt8, UInt8, UInt8) {
        let yValue = Float(yPlane.advanced(by: y * yStride + x)
            .assumingMemoryBound(to: UInt8.self).pointee)
        let cbcrOffset = (y / 2) * cbcrStride + (x / 2) * 2
        let cb = Float(cbcrPlane.advanced(by: cbcrOffset)
            .assumingMemoryBound(to: UInt8.self).pointee) - 128.0
        let cr = Float(cbcrPlane.advanced(by: cbcrOffset + 1)
            .assumingMemoryBound(to: UInt8.self).pointee) - 128.0

        let r = yValue + 1.402 * cr
        let g = yValue - 0.344136 * cb - 0.714136 * cr
        let b = yValue + 1.772 * cb

        return (
            UInt8(clamping: Int(r)),
            UInt8(clamping: Int(g)),
            UInt8(clamping: Int(b))
        )
    }

    // MARK: - Depth Sampling (max of neighbors)

    private func sampleDepth(
        depthBase: UnsafeMutableRawPointer,
        bytesPerRow: Int,
        width: Int, height: Int,
        x: Float, y: Float
    ) -> Float {
        let x0 = Int(x)
        let y0 = Int(y)
        let x1 = min(x0 + 1, width - 1)
        let y1 = min(y0 + 1, height - 1)

        func depthAt(_ col: Int, _ row: Int) -> Float {
            depthBase.advanced(by: row * bytesPerRow + col * MemoryLayout<Float32>.size)
                .assumingMemoryBound(to: Float32.self).pointee
        }

        let d00 = depthAt(x0, y0)
        let d10 = depthAt(x1, y0)
        let d01 = depthAt(x0, y1)
        let d11 = depthAt(x1, y1)

        var maxDepth: Float = 0
        if d00 > 0 { maxDepth = max(maxDepth, d00) }
        if d10 > 0 { maxDepth = max(maxDepth, d10) }
        if d01 > 0 { maxDepth = max(maxDepth, d01) }
        if d11 > 0 { maxDepth = max(maxDepth, d11) }
        return maxDepth
    }
}
