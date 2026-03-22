import SwiftUI

struct GenerateClimbSheet: View {
    let wallId: Int
    let wallImageUrl: String?
    var onGenerated: ([Climb]) -> Void
    var onDismiss: (() -> Void)?

    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var difficultyStep: Double = 1
    @State private var selectedStyle = "static"
    @State private var isGenerating = false
    @State private var errorMessage: String?
    @State private var generatedClimbs: [Climb] = []
    @State private var selectedIndex = 0
    @State private var lastGeneratedDifficulty: Double = -1
    @State private var lastGeneratedStyle: String = ""

    private let styles = ["static", "random", "dynamic"]

    private var difficulty: String {
        switch difficultyStep {
        case 0: return "easy"
        case 1: return "medium"
        default: return "hard"
        }
    }

    private var apiStyle: String {
        if selectedStyle == "random" {
            return Bool.random() ? "static" : "dynamic"
        }
        return selectedStyle
    }

    var body: some View {
        VStack(spacing: 12) {
            // Close button
            HStack {
                Spacer()
                Button {
                    if let onDismiss {
                        onDismiss()
                    } else {
                        dismiss()
                    }
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(Color.sasquatchText)
                        .frame(width: 28, height: 28)
                        .contentShape(Rectangle())
                }
            }
            .padding(.bottom, -8)

            // Wall image
            wallImage

            // Preferences heading
            Text("Preferences")
                .font(.sasquatchHeading(18))
                .foregroundStyle(Color.sasquatchText)
                .frame(maxWidth: .infinity, alignment: .center)

            // Difficulty slider
            difficultySlider

            // Style segmented control
            styleControl

            if let errorMessage {
                Text(errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            // Generate / post-generation buttons
            if generatedClimbs.isEmpty {
                generateButton
            } else {
                postGenerationButtons
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .padding(.bottom, 20)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .padding(.horizontal, 24)
    }

    // MARK: - Subviews

    private var selectedClimb: Climb? {
        guard !generatedClimbs.isEmpty, selectedIndex < generatedClimbs.count else { return nil }
        return generatedClimbs[selectedIndex]
    }

    // Show selected climb image if available, otherwise wall image
    private var displayImageUrl: String? {
        if let climbUrl = selectedClimb?.climbImgUrl {
            return climbUrl
        }
        return wallImageUrl
    }

    @ViewBuilder
    private var wallImage: some View {
        if let urlStr = displayImageUrl, let url = URL(string: urlStr) {
            CachedAsyncImage(url: url) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity)
            } placeholder: {
                wallImagePlaceholder
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .id(urlStr) // Force reload when URL changes
        } else {
            wallImagePlaceholder
                .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private var wallImagePlaceholder: some View {
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
            Image(systemName: "mountain.2.fill")
                .font(.system(size: 40))
                .foregroundStyle(.white.opacity(0.8))
        }
        .frame(height: 378)
    }

    private var difficultySlider: some View {
        VStack(spacing: 4) {
            // Custom slider track + thumb
            GeometryReader { geo in
                let trackHeight: CGFloat = 6
                let thumbSize: CGFloat = 20
                let usableWidth = geo.size.width - thumbSize
                let thumbX = thumbSize / 2 + usableWidth * (difficultyStep / 2)

                ZStack(alignment: .leading) {
                    // Track
                    Capsule()
                        .fill(Color.sasquatchSent.opacity(0.5))
                        .frame(height: trackHeight)
                        .frame(maxWidth: .infinity)
                        .padding(.horizontal, thumbSize / 2)

                    // Thumb
                    Circle()
                        .fill(.white)
                        .overlay(
                            Circle()
                                .stroke(Color.sasquatchText, lineWidth: 2)
                        )
                        .frame(width: thumbSize, height: thumbSize)
                        .position(x: thumbX, y: geo.size.height / 2)
                        .gesture(
                            DragGesture(minimumDistance: 0)
                                .onChanged { value in
                                    let fraction = (value.location.x - thumbSize / 2) / usableWidth
                                    let clamped = min(max(fraction, 0), 1)
                                    let stepped = (clamped * 2).rounded()
                                    withAnimation(.easeInOut(duration: 0.1)) {
                                        difficultyStep = stepped
                                    }
                                }
                        )
                }
            }
            .frame(height: 28)

            HStack {
                Text("Easy")
                Spacer()
                Text("Difficult")
            }
            .font(.sasquatchBody(12))
            .fontWeight(.semibold)
            .foregroundStyle(Color.sasquatchText)
        }
        .padding(.horizontal, 10)
    }

    private var styleControl: some View {
        HStack(spacing: 4) {
            ForEach(styles, id: \.self) { style in
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        selectedStyle = style
                    }
                } label: {
                    Text(style.capitalized)
                        .font(selectedStyle == style ? .sasquatchButton(13) : .sasquatchBody(13))
                        .fontWeight(selectedStyle == style ? .bold : .semibold)
                        .foregroundStyle(Color.sasquatchText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 32)
                        .background(
                            selectedStyle == style
                                ? AnyShapeStyle(.white)
                                : AnyShapeStyle(.clear)
                        )
                        .clipShape(Capsule())
                }
            }
        }
        .padding(2)
        .background(Color.sasquatchSent.opacity(0.5))
        .clipShape(Capsule())
    }

    private var generateButton: some View {
        Button {
            Task { await generate() }
        } label: {
            HStack(spacing: 8) {
                if isGenerating {
                    ProgressView()
                        .tint(Color.sasquatchText)
                }
                Text(isGenerating ? "Generating..." : "Generate")
                    .font(.sasquatchButton(16))
            }
            .foregroundStyle(Color.sasquatchText)
            .frame(width: 151, height: 44)
            .background(.white)
            .clipShape(Capsule())
            .overlay(
                Capsule().stroke(Color.sasquatchAccent, lineWidth: 2)
            )
        }
        .disabled(isGenerating)
    }

    private var postGenerationButtons: some View {
        VStack(spacing: 12) {
            // Route indicator
            if generatedClimbs.count > 1 {
                Text("Route \(selectedIndex + 1) of \(generatedClimbs.count)")
                    .font(.sasquatchMedium(14))
                    .foregroundStyle(Color.sasquatchText.opacity(0.6))
            }

            HStack(spacing: 12) {
                // Try again — re-generate if settings changed, otherwise cycle
                Button {
                    if difficultyStep != lastGeneratedDifficulty || selectedStyle != lastGeneratedStyle {
                        generatedClimbs = []
                        Task { await generate() }
                    } else {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedIndex = (selectedIndex + 1) % generatedClimbs.count
                        }
                    }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "arrow.counterclockwise")
                            .font(.system(size: 18))
                        Text("Try again")
                            .font(.sasquatchBody(16))
                    }
                    .foregroundStyle(Color.sasquatchText)
                    .frame(width: 151, height: 44)
                    .background(.white)
                    .clipShape(Capsule())
                    .overlay(
                        Capsule().stroke(Color.sasquatchAccent, lineWidth: 2)
                    )
                }

                // Let's go! — accept selected climb
                Button {
                    if let climb = selectedClimb {
                        onGenerated([climb])
                    }
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "checkmark")
                            .font(.system(size: 20, weight: .semibold))
                        Text("Let's go!")
                            .font(.sasquatchButton(16))
                    }
                    .foregroundStyle(.white)
                    .frame(width: 151, height: 44)
                    .background(Color.sasquatchSent)
                    .clipShape(Capsule())
                }
            }
        }
    }

    // MARK: - Action

    private func generate() async {
        isGenerating = true
        errorMessage = nil
        do {
            let climbs = try await api.generateClimbs(
                wallId: wallId,
                difficulty: difficulty,
                style: apiStyle,
                topK: 20
            )
            if climbs.isEmpty {
                errorMessage = "No routes found for this difficulty. Try a different setting."
            } else {
                generatedClimbs = climbs
                selectedIndex = 0
                lastGeneratedDifficulty = difficultyStep
                lastGeneratedStyle = selectedStyle
            }
        } catch {
            errorMessage = "Generation failed: \(error.localizedDescription)"
        }
        isGenerating = false
    }
}

#Preview {
    ZStack {
        Color.black.opacity(0.5).ignoresSafeArea()
        GenerateClimbSheet(
            wallId: 1,
            wallImageUrl: nil,
            onGenerated: { _ in },
            onDismiss: { }
        )
        .environment(APIClient())
    }
}
