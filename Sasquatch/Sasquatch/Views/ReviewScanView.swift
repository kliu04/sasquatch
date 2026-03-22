import SwiftUI

struct ReviewScanView: View {
    let wallId: Int
    var onRetake: () -> Void
    var onDone: ((Int) -> Void)?

    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var wall: Wall?
    @State private var holds: [Hold] = []
    @State private var isProcessing = true
    @State private var errorMessage: String?
    @State private var wallName = ""
    @State private var isRenaming = false

    var body: some View {
        ZStack(alignment: .top) {
            Color.sasquatchBackground
                .ignoresSafeArea()

            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 20) {
                    // Back button
                    Button { dismiss() } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 16, weight: .medium))
                            .foregroundStyle(Color.sasquatchTextSecondary)
                            .frame(width: 40, height: 40)
                            .background(.white)
                            .clipShape(Circle())
                            .overlay(Circle().stroke(Color.sasquatchTextSecondary, lineWidth: 1))
                    }
                    .padding(.top, 16)

                    // Heading
                    Text("review scan")
                        .font(.system(size: 30, weight: .heavy))
                        .foregroundStyle(Color.sasquatchTextSecondary)
                        .tracking(-0.6)

                    // Main image card
                    imageCard

                    // Wall name input
                    wallNameInput

                    // Action buttons
                    actionButtons
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .task { await pollForProcessing() }
    }

    // MARK: - Image Card

    private var imageCard: some View {
        ZStack(alignment: .bottom) {
            // Show holds overlay image when ready, else wall image
            if let holdsUrl = wall?.holdsImageUrl, let url = URL(string: holdsUrl) {
                CachedAsyncImage(url: url) { image in
                    image.resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(maxWidth: .infinity, maxHeight: 400)
                } placeholder: {
                    imagePlaceholder
                }
            } else if let imgUrl = wall?.wallImgUrl, let url = URL(string: imgUrl) {
                CachedAsyncImage(url: url) { image in
                    image.resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(maxWidth: .infinity, maxHeight: 400)
                } placeholder: {
                    imagePlaceholder
                }
            } else {
                imagePlaceholder
            }

            // Status banner (only show when not processing — placeholder handles that)
            if !isProcessing {
                statusBanner
                    .padding(12)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
        )
    }

    private var imagePlaceholder: some View {
        RoundedRectangle(cornerRadius: 0)
            .fill(Color.sasquatchBackground)
            .frame(height: 300)
            .overlay {
                if isProcessing {
                    VStack(spacing: 12) {
                        ProgressView()
                            .scaleEffect(1.3)
                        Text("Detecting holds...")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(Color.sasquatchTextSecondary)
                    }
                }
            }
    }

    @ViewBuilder
    private var statusBanner: some View {
        HStack(spacing: 8) {
            if isProcessing {
                ProgressView()
                    .scaleEffect(0.8)
            } else if wall?.status == .error {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
            } else {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(Color.sasquatchSent)
            }
            Text(bannerText)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(Color.sasquatchTextSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .padding(.horizontal, 12)
        .background(.white.opacity(0.9))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var bannerText: String {
        if isProcessing { return "Detecting holds..." }
        if wall?.status == .error { return wall?.errorMessage ?? "Processing failed" }
        if let count = wall?.holdCount { return "Wall scanned • \(count) holds detected" }
        return "Ready"
    }

    // MARK: - Wall Name

    private var wallNameInput: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Wall name")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(Color.sasquatchTextSecondary)

            TextField("e.g., North Wall", text: $wallName)
                .font(.system(size: 16))
                .foregroundStyle(Color.sasquatchTextSecondary)
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
                .background(.white)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                )
        }
    }

    // MARK: - Buttons

    private var actionButtons: some View {
        HStack(spacing: 16) {
            Button { onRetake() } label: {
                HStack(spacing: 6) {
                    Image(systemName: "arrow.counterclockwise")
                        .font(.system(size: 16))
                    Text("retake")
                        .font(.system(size: 16, weight: .semibold))
                }
                .foregroundStyle(Color.sasquatchTextSecondary)
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(.white)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                )
            }

            Button {
                Task { await navigateToWall() }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark")
                        .font(.system(size: 16, weight: .semibold))
                    Text("done")
                        .font(.system(size: 16, weight: .semibold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 56)
                .background(isProcessing ? Color.gray : Color.sasquatchTextSecondary)
                .clipShape(RoundedRectangle(cornerRadius: 16))
            }
            .disabled(isProcessing)
        }
    }

    // MARK: - Polling

    private func pollForProcessing() async {
        isProcessing = true
        do {
            // Long-poll until ready or error
            while true {
                let w = try await api.getWall(wallId, poll: true, timeout: 30)
                wall = w
                wallName = w.name
                if w.status == .ready || w.status == .error {
                    break
                }
            }

            // Fetch holds if ready
            if wall?.status == .ready {
                let response = try await api.getHolds(wallId: wallId)
                holds = response.holds
            }
        } catch {
            errorMessage = error.localizedDescription
            print("Polling failed: \(error)")
        }
        isProcessing = false
    }

    private func navigateToWall() async {
        if let onDone {
            onDone(wallId)
        } else {
            dismiss()
        }
    }
}

#Preview {
    ReviewScanView(wallId: 1, onRetake: {})
        .environment(APIClient())
}
