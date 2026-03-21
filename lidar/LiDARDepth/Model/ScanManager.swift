import Foundation
import ARKit
import CoreVideo
import UIKit

class ScanManager: ObservableObject {
    @Published var isRecording = false
    @Published var isExporting = false
    @Published var exportedFileURL: URL?
    @Published var meshAnchorCount = 0

    weak var arSession: ARSession?

    private var capturedMeshAnchors: [ARMeshAnchor] = []
    private var capturedFrame: ARFrame?

    func startRecording() {
        capturedMeshAnchors.removeAll()
        capturedFrame = nil
        exportedFileURL = nil
        meshAnchorCount = 0
        isRecording = true
    }

    func stopRecording() {
        isRecording = false
        guard let frame = arSession?.currentFrame else { return }
        capturedFrame = frame
        capturedMeshAnchors = frame.anchors.compactMap { $0 as? ARMeshAnchor }
        meshAnchorCount = capturedMeshAnchors.count
    }

    var hasMeshData: Bool {
        !capturedMeshAnchors.isEmpty
    }

    func exportPLY() {
        guard !capturedMeshAnchors.isEmpty else { return }
        isExporting = true

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self = self else { return }
            do {
                let url = try self.writePLY()
                DispatchQueue.main.async {
                    self.exportedFileURL = url
                    self.isExporting = false
                }
            } catch {
                print("PLY export failed: \(error)")
                DispatchQueue.main.async {
                    self.isExporting = false
                }
            }
        }
    }

    // MARK: - PLY Writing

    private func writePLY() throws -> URL {
        var allVertices: [(x: Float, y: Float, z: Float, r: UInt8, g: UInt8, b: UInt8)] = []
        var allFaces: [(Int, Int, Int)] = []
        var vertexOffset = 0

        // Prepare color sampling from captured camera frame
        let colorSampler = capturedFrame.flatMap { ColorSampler(frame: $0) }

        for anchor in capturedMeshAnchors {
            let geometry = anchor.geometry
            let transform = anchor.transform

            let vertexBuffer = geometry.vertices.buffer.contents()
            let normalBuffer = geometry.normals.buffer.contents()

            for i in 0..<geometry.vertices.count {
                let vertexPtr = vertexBuffer.advanced(by: geometry.vertices.offset + geometry.vertices.stride * i)
                let vertex = vertexPtr.assumingMemoryBound(to: SIMD3<Float>.self).pointee

                // Transform to world space
                let worldPos = transform * SIMD4<Float>(vertex.x, vertex.y, vertex.z, 1.0)

                // Sample color
                let (r, g, b) = colorSampler?.sampleColor(at: SIMD3<Float>(worldPos.x, worldPos.y, worldPos.z)) ?? (128, 128, 128)

                allVertices.append((worldPos.x, worldPos.y, worldPos.z, r, g, b))
            }

            // Read faces
            let faceBuffer = geometry.faces.buffer.contents()
            let bytesPerIndex = geometry.faces.bytesPerIndex

            for i in 0..<geometry.faces.count {
                let facePtr = faceBuffer.advanced(by: bytesPerIndex * 3 * i)

                let idx0, idx1, idx2: Int
                if bytesPerIndex == 4 {
                    let ptr = facePtr.assumingMemoryBound(to: UInt32.self)
                    idx0 = Int(ptr[0]) + vertexOffset
                    idx1 = Int(ptr[1]) + vertexOffset
                    idx2 = Int(ptr[2]) + vertexOffset
                } else {
                    let ptr = facePtr.assumingMemoryBound(to: UInt16.self)
                    idx0 = Int(ptr[0]) + vertexOffset
                    idx1 = Int(ptr[1]) + vertexOffset
                    idx2 = Int(ptr[2]) + vertexOffset
                }
                allFaces.append((idx0, idx1, idx2))
            }

            vertexOffset += geometry.vertices.count
        }

        // Write PLY
        let fileName = "scan_\(Int(Date().timeIntervalSince1970)).ply"
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(fileName)

        var ply = """
        ply
        format ascii 1.0
        element vertex \(allVertices.count)
        property float x
        property float y
        property float z
        property uchar red
        property uchar green
        property uchar blue
        element face \(allFaces.count)
        property list uchar int vertex_indices
        end_header\n
        """

        for v in allVertices {
            ply += "\(v.x) \(v.y) \(v.z) \(v.r) \(v.g) \(v.b)\n"
        }
        for f in allFaces {
            ply += "3 \(f.0) \(f.1) \(f.2)\n"
        }

        try ply.write(to: url, atomically: true, encoding: .utf8)
        return url
    }
}

// MARK: - Color Sampling from Camera Frame

private class ColorSampler {
    let camera: ARCamera
    let pixelBuffer: CVPixelBuffer
    let imageWidth: Int
    let imageHeight: Int
    let viewportSize: CGSize

    init?(frame: ARFrame) {
        self.camera = frame.camera
        self.pixelBuffer = frame.capturedImage
        self.imageWidth = CVPixelBufferGetWidth(pixelBuffer)
        self.imageHeight = CVPixelBufferGetHeight(pixelBuffer)
        // Use landscape dimensions since camera captures in landscape
        self.viewportSize = CGSize(width: imageWidth, height: imageHeight)
    }

    func sampleColor(at worldPoint: SIMD3<Float>) -> (UInt8, UInt8, UInt8) {
        // Project 3D world point to 2D image coordinates
        let projected = camera.projectPoint(worldPoint, orientation: .landscapeRight, viewportSize: viewportSize)

        let px = Int(projected.x)
        let py = Int(projected.y)

        guard px >= 0 && px < imageWidth && py >= 0 && py < imageHeight else {
            return (128, 128, 128) // default gray for out-of-frame vertices
        }

        return samplePixel(x: px, y: py)
    }

    private func samplePixel(x: Int, y: Int) -> (UInt8, UInt8, UInt8) {
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }

        // Camera frames are YCbCr (420v/420f). Sample Y plane for luminance,
        // CbCr plane for chroma, then convert to RGB.
        guard let yPlane = CVPixelBufferGetBaseAddressOfPlane(pixelBuffer, 0),
              let cbcrPlane = CVPixelBufferGetBaseAddressOfPlane(pixelBuffer, 1) else {
            return (128, 128, 128)
        }

        let yStride = CVPixelBufferGetBytesPerRowOfPlane(pixelBuffer, 0)
        let cbcrStride = CVPixelBufferGetBytesPerRowOfPlane(pixelBuffer, 1)

        let yValue = Float(yPlane.advanced(by: y * yStride + x).assumingMemoryBound(to: UInt8.self).pointee)
        let cbcrOffset = (y / 2) * cbcrStride + (x / 2) * 2
        let cb = Float(cbcrPlane.advanced(by: cbcrOffset).assumingMemoryBound(to: UInt8.self).pointee) - 128.0
        let cr = Float(cbcrPlane.advanced(by: cbcrOffset + 1).assumingMemoryBound(to: UInt8.self).pointee) - 128.0

        // YCbCr to RGB (BT.601)
        let r = yValue + 1.402 * cr
        let g = yValue - 0.344136 * cb - 0.714136 * cr
        let b = yValue + 1.772 * cb

        return (
            UInt8(clamping: Int(r)),
            UInt8(clamping: Int(g)),
            UInt8(clamping: Int(b))
        )
    }
}
