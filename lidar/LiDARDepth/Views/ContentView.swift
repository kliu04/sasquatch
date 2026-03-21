import SwiftUI

struct ContentView: View {
    @StateObject private var scanManager = ScanManager()
    @State private var showShareSheet = false

    var body: some View {
        ZStack {
            ARViewContainer(scanManager: scanManager)
                .edgesIgnoringSafeArea(.all)

            VStack {
                Spacer()

                if scanManager.isExporting {
                    ProgressView("Exporting...")
                        .padding(12)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
                        .padding(.bottom, 8)
                }

                HStack(spacing: 40) {
                    // Capture
                    Button {
                        scanManager.capture()
                    } label: {
                        Image(systemName: "camera.circle.fill")
                            .font(.system(size: 64))
                            .foregroundColor(.white)
                    }

                    // Export PLY + PNG
                    Button {
                        scanManager.export()
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: "square.and.arrow.up")
                                .font(.system(size: 28))
                            Text("Export")
                                .font(.caption)
                        }
                        .foregroundColor(.white)
                    }
                    .disabled(!scanManager.hasMeshData || scanManager.isExporting)
                    .opacity(scanManager.hasMeshData ? 1.0 : 0.4)
                }
                .padding(.bottom, 40)
            }
        }
        .onChange(of: scanManager.exportedFiles) { files in
            if !files.isEmpty {
                showShareSheet = true
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if !scanManager.exportedFiles.isEmpty {
                ShareSheet(items: scanManager.exportedFiles)
            }
        }
    }
}

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
