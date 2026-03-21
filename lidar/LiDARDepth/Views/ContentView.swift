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

                if scanManager.isRecording {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(.red)
                            .frame(width: 10, height: 10)
                        Text("Recording...")
                            .font(.subheadline)
                            .foregroundColor(.white)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(.bottom, 8)
                }

                if scanManager.isExporting {
                    ProgressView("Exporting...")
                        .padding(12)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8))
                        .padding(.bottom, 8)
                }

                HStack(spacing: 40) {
                    // Record / Stop
                    Button {
                        if scanManager.isRecording {
                            scanManager.stopRecording()
                        } else {
                            scanManager.startRecording()
                        }
                    } label: {
                        Image(systemName: scanManager.isRecording ? "stop.circle.fill" : "record.circle")
                            .font(.system(size: 64))
                            .foregroundColor(scanManager.isRecording ? .red : .white)
                    }

                    // Export PLY
                    Button {
                        scanManager.exportPLY()
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: "square.and.arrow.up")
                                .font(.system(size: 28))
                            Text("Export PLY")
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
        .onChange(of: scanManager.exportedFileURL) { url in
            if url != nil {
                showShareSheet = true
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = scanManager.exportedFileURL {
                ShareSheet(items: [url])
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
