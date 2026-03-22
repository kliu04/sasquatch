import SwiftUI

struct WallDetailView: View {
    let wallId: Int
    private var previewWall: Wall?
    private var previewClimbs: [Climb]?

    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var wall: Wall?
    @State private var climbs: [Climb] = []
    @State private var generatedClimbs: [Climb] = []
    @State private var isLoading = true
    @State private var showGenerateSheet = false
    @State private var showClimbPicker = false
    @State private var showShareSheet = false
    @State private var shareItems: [Any] = []
    @State private var isGeneratingClimb = false

    init(wallId: Int, previewWall: Wall? = nil, previewClimbs: [Climb]? = nil) {
        self.wallId = wallId
        self.previewWall = previewWall
        self.previewClimbs = previewClimbs
    }

    var body: some View {
        ZStack(alignment: .top) {
            Color.sasquatchBackground
                .ignoresSafeArea()

            // Blue header band
            Color.sasquatchBlue
                .frame(height: 160)
                .ignoresSafeArea(edges: .top)

            // Scrollable content
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 24) {
                    // Back button
                    Button { dismiss() } label: {
                        Image(systemName: "arrow.left")
                            .font(.system(size: 20, weight: .medium))
                            .foregroundStyle(Color.sasquatchText)
                            .frame(width: 44, height: 44)
                            .contentShape(Rectangle())
                    }
                    .padding(.top, 4)
                    .padding(.bottom, -16)

                    // Wall name
                    Text(wall?.name.uppercased() ?? "")
                        .font(.sasquatchTitle(30))
                        .foregroundStyle(Color.sasquatchText)

                    // Wall image
                    wallImageSection.padding(.top, 20)

                    // Generate new climb button
                    generateButton

                    // Saved climbs section
                    savedClimbsSection
                }
                .padding(.horizontal, 30)
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .task { await loadData() }
        .overlay {
            if showGenerateSheet {
                Color.black.opacity(0.5)
                    .ignoresSafeArea()
                    .onTapGesture { showGenerateSheet = false }

                GenerateClimbSheet(
                    wallId: wallId,
                    wallImageUrl: wall?.wallImgUrl,
                    onGenerated: { newClimbs in
                        if newClimbs.isEmpty {
                            // Route generation found no valid routes — stay on generate sheet
                            return
                        }
                        generatedClimbs = newClimbs
                        showGenerateSheet = false
                        showClimbPicker = true
                    },
                    onDismiss: { showGenerateSheet = false }
                )
                .environment(api)
                .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.25), value: showGenerateSheet)
        .overlay {
            if showClimbPicker && !generatedClimbs.isEmpty {
                Color.black.opacity(0.5)
                    .ignoresSafeArea()

                ClimbPickerSheet(
                    climbs: generatedClimbs,
                    wallId: wallId,
                    onShare: { items in
                        shareItems = items
                        showShareSheet = true
                    },
                    onSave: {
                        showClimbPicker = false
                        generatedClimbs = []
                        Task { await refreshClimbs() }
                    },
                    onDismiss: {
                        showClimbPicker = false
                        generatedClimbs = []
                    }
                )
                .environment(api)
                .transition(.opacity.combined(with: .scale(scale: 0.95)))
            }
        }
        .animation(.easeInOut(duration: 0.25), value: showClimbPicker)
        .background(SharePresenter(isPresented: $showShareSheet, items: shareItems))
        .overlay {
            if isGeneratingClimb {
                climbGenerationLoadingScreen
            }
        }
        .animation(.easeInOut(duration: 0.25), value: isGeneratingClimb)
    }

    // MARK: - Subviews

    @ViewBuilder
    private var wallImageSection: some View {
        if let imageUrl = wall?.wallImgUrl, let url = URL(string: imageUrl) {
            CachedAsyncImage(url: url) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(maxWidth: .infinity)
                    .frame(height: 331)
                    .clipped()
            } placeholder: {
                imagePlaceholder(icon: nil)
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
        } else if wall != nil {
            // Preview / no image URL — show a colorful mock
            ZStack {
                LinearGradient(
                    colors: [
                        Color(red: 0.56, green: 0.72, blue: 0.79),
                        Color(red: 0.85, green: 0.65, blue: 0.45),
                        Color(red: 0.48, green: 0.56, blue: 0.27)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                VStack(spacing: 8) {
                    Image(systemName: "mountain.2.fill")
                        .font(.system(size: 48))
                    Text("Wall Image")
                        .font(.sasquatchBody())
                }
                .foregroundStyle(.white.opacity(0.9))
            }
            .frame(height: 331)
            .clipShape(RoundedRectangle(cornerRadius: 8))
        } else if isLoading {
            imagePlaceholder(icon: nil)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private func imagePlaceholder(icon: String?) -> some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.gray.opacity(0.1))
            .frame(height: 331)
            .overlay {
                if let icon {
                    Image(systemName: icon)
                        .font(.largeTitle)
                        .foregroundStyle(.gray)
                } else {
                    ProgressView()
                }
            }
    }

    private var generateButton: some View {
        Button { showGenerateSheet = true } label: {
            HStack(spacing: 8) {
                Image(systemName: "sparkles")
                    .font(.system(size: 20))
                Text("Generate new climb")
                    .font(.sasquatchButton())
            }
            .frame(maxWidth: .infinity)
            .frame(height: 48)
            .foregroundStyle(Color.sasquatchText)
            .background(.white)
            .clipShape(Capsule())
            .overlay(
                Capsule().stroke(Color.sasquatchBlue, lineWidth: 2)
            )
        }
    }

    private var savedClimbsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Saved climbs")
                .font(.sasquatchHeading(20))
                .foregroundStyle(Color.sasquatchTextSecondary)

            if climbs.isEmpty && !isLoading {
                Text("No saved climbs yet")
                    .font(.system(size: 14))
                    .foregroundStyle(.gray)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 24)
            }

            VStack(spacing: 8) {
                ForEach(climbs) { climb in
                    NavigationLink {
                        ClimbDetailView(climb: climb, wallName: wall?.name ?? "")
                            .environment(api)
                    } label: {
                        ClimbCard(climb: climb)
                            .frame(height: 73)
                            .clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var climbGenerationLoadingScreen: some View {
        ZStack {
            Color.sasquatchBlue
                .ignoresSafeArea()

            VStack(spacing: 16) {
                Image("sasquatch_searching")
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 211)

                Text("Generating climb...")
                    .font(.sasquatchTitle(20))
                    .foregroundStyle(Color.sasquatchText)
                    .tracking(-0.6)
            }
        }
    }

    // MARK: - Data

    private func loadData() async {
        if let previewWall {
            wall = previewWall
            climbs = previewClimbs ?? []
            isLoading = false
            return
        }
        do {
            async let wallData = api.getWall(wallId)
            async let climbsData = api.getSavedClimbs(wallId: wallId)
            wall = try await wallData
            climbs = try await climbsData
        } catch {
            print("Failed to load wall: \(error)")
        }
        isLoading = false
    }

    private func refreshClimbs() async {
        do {
            climbs = try await api.getSavedClimbs(wallId: wallId)
        } catch {
            print("Failed to refresh climbs: \(error)")
        }
    }
}

#Preview {
    WallDetailView(
        wallId: 1,
        previewWall: PreviewData.wall,
        previewClimbs: PreviewData.climbs
    )
    .environment(APIClient())
}
