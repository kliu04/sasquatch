import SwiftUI

struct ScanCaptureView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(APIClient.self) private var api
    @State private var scanManager = ScanManager()
    @State private var wallId: Int?
    @State private var isUploading = false
    @State private var uploadStatus = ""
    @State private var errorMessage: String?
    @State private var navigateToReview = false

    var body: some View {
        ZStack {
            Color(red: 0.25, green: 0.25, blue: 0.25)
                .ignoresSafeArea()

            VStack(spacing: 32) {
                // Camera viewfinder
                ZStack {
                    ARViewContainer(scanManager: scanManager)
                        .clipShape(RoundedRectangle(cornerRadius: 16))

                    gridOverlay

                    // Instruction text
                    if !scanManager.hasCaptured && !isUploading {
                        VStack(spacing: 8) {
                            Text("Frame the climbing wall")
                                .font(.system(size: 18, weight: .semibold))
                                .foregroundStyle(.white)
                            Text("Make sure the entire wall is visible")
                                .font(.system(size: 14))
                                .foregroundStyle(.white.opacity(0.7))
                            if !scanManager.hasLiDAR {
                                Text("Camera only — no LiDAR depth")
                                    .font(.system(size: 12, weight: .medium))
                                    .foregroundStyle(.orange.opacity(0.9))
                                    .padding(.top, 4)
                            }
                        }
                    }

                    // Upload/processing overlay
                    if isUploading || scanManager.isExporting {
                        Color.black.opacity(0.6)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                        VStack(spacing: 12) {
                            ProgressView()
                                .tint(.white)
                                .scaleEffect(1.5)
                            Text(scanManager.isExporting ? "Processing scan..." : uploadStatus)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(.white)
                        }
                    }

                    // Error
                    if let errorMessage {
                        VStack(spacing: 12) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .font(.system(size: 32))
                                .foregroundStyle(.orange)
                            Text(errorMessage)
                                .font(.system(size: 14, weight: .medium))
                                .foregroundStyle(.white)
                                .multilineTextAlignment(.center)
                            Button("Try again") {
                                self.errorMessage = nil
                                scanManager.hasCaptured = false
                            }
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 8)
                            .background(.white.opacity(0.2))
                            .clipShape(Capsule())
                        }
                        .padding(24)
                    }
                }
                .frame(height: 472)

                // Capture button
                captureButton
            }
            .padding(.horizontal, 24)

            // Back button
            VStack {
                HStack {
                    Button { dismiss() } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 18, weight: .medium))
                            .foregroundStyle(.white)
                            .frame(width: 40, height: 40)
                            .background(.white.opacity(0.2))
                            .clipShape(Circle())
                    }
                    Spacer()
                }
                .padding(.horizontal, 24)
                .padding(.top, 16)
                Spacer()
            }
        }
        .navigationBarHidden(true)
        .onAppear { scanManager.checkLiDAR() }
        .onChange(of: scanManager.exportedFiles) { _, files in
            if !files.isEmpty {
                Task { await uploadAndProcess(files: files) }
            }
        }
        .navigationDestination(isPresented: $navigateToReview) {
            if let wallId {
                ReviewScanView(wallId: wallId, onRetake: {
                    navigateToReview = false
                    self.wallId = nil
                    scanManager.exportedFiles = []
                    scanManager.hasCaptured = false
                    errorMessage = nil
                })
                .environment(api)
            }
        }
    }

    // MARK: - Upload flow

    private func uploadAndProcess(files: [URL]) async {
        isUploading = true
        errorMessage = nil
        do {
            // 1. Create wall
            uploadStatus = "Creating wall..."
            let response = try await api.createWall(name: "Wall \(Int(Date().timeIntervalSince1970) % 10000)")

            // 2. Upload PLY
            if let plyURL = files.first(where: { $0.pathExtension == "ply" }) {
                uploadStatus = "Uploading point cloud..."
                let plyData = try Data(contentsOf: plyURL)
                try await api.uploadFile(to: response.plyUploadUrl, data: plyData, contentType: "application/octet-stream")
            }

            // 3. Upload PNG
            if let pngURL = files.first(where: { $0.pathExtension == "png" }) {
                uploadStatus = "Uploading image..."
                let pngData = try Data(contentsOf: pngURL)
                try await api.uploadFile(to: response.pngUploadUrl, data: pngData, contentType: "image/png")
            }

            // 4. Trigger processing
            uploadStatus = "Starting hold detection..."
            try await api.triggerProcessing(wallId: response.id)

            // 5. Navigate to review
            wallId = response.id
            navigateToReview = true
        } catch {
            errorMessage = error.localizedDescription
            print("Upload failed: \(error)")
        }
        isUploading = false
    }

    // MARK: - Subviews

    private var gridOverlay: some View {
        GeometryReader { geo in
            Path { path in
                let thirdW = geo.size.width / 3
                let thirdH = geo.size.height / 3
                path.move(to: CGPoint(x: thirdW, y: 0))
                path.addLine(to: CGPoint(x: thirdW, y: geo.size.height))
                path.move(to: CGPoint(x: thirdW * 2, y: 0))
                path.addLine(to: CGPoint(x: thirdW * 2, y: geo.size.height))
                path.move(to: CGPoint(x: 0, y: thirdH))
                path.addLine(to: CGPoint(x: geo.size.width, y: thirdH))
                path.move(to: CGPoint(x: 0, y: thirdH * 2))
                path.addLine(to: CGPoint(x: geo.size.width, y: thirdH * 2))
            }
            .stroke(.white.opacity(0.15), lineWidth: 0.5)
        }
    }

    private var captureButton: some View {
        Button {
            scanManager.capture()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                scanManager.export()
            }
        } label: {
            ZStack {
                Circle().fill(.white).frame(width: 80, height: 80)
                    .overlay(Circle().stroke(Color(red: 0.44, green: 0.75, blue: 0.98), lineWidth: 3))
                Circle().fill(.white).frame(width: 64, height: 64)
                    .overlay(Circle().stroke(Color(red: 0.25, green: 0.25, blue: 0.25), lineWidth: 1))
                Image(systemName: "camera.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(Color(red: 0.25, green: 0.25, blue: 0.25))
            }
        }
        .disabled(scanManager.isExporting || isUploading || errorMessage != nil)
        .opacity((scanManager.isExporting || isUploading) ? 0.5 : 1)
    }
}
