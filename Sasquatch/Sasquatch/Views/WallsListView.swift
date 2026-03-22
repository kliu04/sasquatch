import SwiftUI

struct WallsListView: View {
    @Environment(APIClient.self) private var api
    @State private var walls: [WallSummary] = []
    @State private var isLoading = true

    var body: some View {
        ZStack(alignment: .top) {
            Color.sasquatchBackground
                .ignoresSafeArea()

            // Blue header band
            Color.sasquatchAccent
                .frame(height: 160)
                .ignoresSafeArea(edges: .top)

            VStack(spacing: 0) {
                // Header with mascot + title
                HStack(spacing: 8) {
                    // Mascot placeholder
                    Image(systemName: "pawprint.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(Color.sasquatchText)
                        .frame(width: 60, height: 60)

                    Text("Saved Walls")
                        .font(.system(size: 32, weight: .black))
                        .foregroundStyle(Color.sasquatchText)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 24)
                .padding(.top, 8)

                // Wall cards list
                if isLoading {
                    Spacer()
                    ProgressView()
                    Spacer()
                } else if walls.isEmpty {
                    Spacer()
                    emptyState
                    Spacer()
                } else {
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 16) {
                            ForEach(walls) { wall in
                                NavigationLink(value: WallDestination.detail(wall.id)) {
                                    WallCard(wall: wall)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(.horizontal, 24)
                        .padding(.top, 16)
                        .padding(.bottom, 100)
                    }
                }
            }
        }
        .navigationBarHidden(true)
        .task { await loadWalls() }
        .refreshable { await loadWalls() }
    }

    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "mountain.2")
                .font(.system(size: 48))
                .foregroundStyle(Color.sasquatchAccent)
            Text("No walls yet")
                .font(.sasquatchHeading())
                .foregroundStyle(Color.sasquatchText)
            Text("Scan a climbing wall with LiDAR to get started")
                .font(.system(size: 14))
                .foregroundStyle(.gray)
                .multilineTextAlignment(.center)
        }
        .padding(40)
    }

    private func loadWalls() async {
        do {
            walls = try await api.getWalls()
        } catch {
            print("Failed to load walls: \(error)")
        }
        isLoading = false
    }
}

// MARK: - Wall Card

struct WallCard: View {
    let wall: WallSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Wall image thumbnail
            if let urlStr = wall.wallImgUrl, let url = URL(string: urlStr) {
                GeometryReader { geo in
                    CachedAsyncImage(url: url) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: geo.size.width, height: geo.size.height)
                    } placeholder: {
                        thumbnailPlaceholder
                    }
                }
                .frame(height: 180)
                .clipShape(RoundedRectangle(cornerRadius: 16))
            } else {
                thumbnailPlaceholder
                    .clipShape(RoundedRectangle(cornerRadius: 16))
            }

            // Bottom row: name + tag
            HStack {
                Text(wall.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Color.sasquatchTextSecondary)

                Spacer()

                // Status tag
                statusTag
            }
        }
        .padding(16)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
        )
        .contentShape(Rectangle())
    }

    private var thumbnailPlaceholder: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color.sasquatchBackground)
            .frame(height: 93)
    }

    @ViewBuilder
    private var statusTag: some View {
        HStack(spacing: 6) {
            Image(systemName: statusIcon)
                .font(.system(size: 8))
            Text(statusLabel)
                .font(.system(size: 8, weight: .semibold))
        }
        .foregroundStyle(Color.sasquatchTextSecondary)
        .padding(6)
        .background(Color.sasquatchAccent.opacity(0.5))
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private var statusIcon: String {
        switch wall.status {
        case .ready: return "checkmark.circle.fill"
        case .processing: return "arrow.triangle.2.circlepath"
        case .pendingUpload: return "arrow.up.circle"
        case .error: return "exclamationmark.triangle.fill"
        }
    }

    private var statusLabel: String {
        switch wall.status {
        case .ready:
            if let count = wall.holdCount, count > 0 {
                return "\(count) holds detected"
            }
            return "Ready"
        case .processing: return "Processing..."
        case .pendingUpload: return "Pending upload"
        case .error: return "Error"
        }
    }
}

#Preview {
    NavigationStack {
        WallsListView()
            .environment(APIClient())
    }
}
