import SwiftUI

struct GenerateClimbSheet: View {
    let wallId: Int
    let wallImageUrl: String?
    var onGenerated: ([Climb]) -> Void

    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var difficultyStep: Double = 1
    @State private var selectedStyle = "static"
    @State private var isGenerating = false
    @State private var errorMessage: String?

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
        VStack(spacing: 16) {
            // Wall image
            wallImage

            // Preferences heading
            Text("Preferences")
                .font(.system(size: 18, weight: .heavy))
                .foregroundStyle(Color.sasquatchTextSecondary)

            // Difficulty slider
            difficultySlider

            // Style segmented control
            styleControl

            if let errorMessage {
                Text(errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }

            // Generate button
            generateButton
        }
        .padding(16)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .padding(.horizontal, 24)
    }

    // MARK: - Subviews

    @ViewBuilder
    private var wallImage: some View {
        if let urlStr = wallImageUrl, let url = URL(string: urlStr) {
            AsyncImage(url: url) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(maxWidth: .infinity)
                        .frame(height: 180)
                        .clipped()
                default:
                    wallImagePlaceholder
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 8))
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
        .frame(height: 180)
    }

    private var difficultySlider: some View {
        VStack(spacing: 4) {
            Slider(value: $difficultyStep, in: 0...2, step: 1)
                .tint(Color.sasquatchAccent)

            HStack {
                Text("Easy")
                Spacer()
                Text("Medium")
                Spacer()
                Text("Hard")
            }
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(Color.sasquatchTextSecondary)
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
                        .font(.system(size: 13, weight: selectedStyle == style ? .bold : .medium))
                        .foregroundStyle(Color.sasquatchTextSecondary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 28)
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
            HStack(spacing: 10) {
                if isGenerating {
                    ProgressView()
                        .tint(Color.sasquatchTextSecondary)
                } else {
                    Image(systemName: "sparkles")
                        .font(.system(size: 20))
                }
                Text(isGenerating ? "Generating..." : "Generate")
                    .font(.system(size: 16, weight: .semibold))
            }
            .foregroundStyle(Color.sasquatchTextSecondary)
            .padding(.horizontal, 40)
            .padding(.vertical, 13)
            .background(.white)
            .clipShape(Capsule())
            .overlay(
                Capsule().stroke(Color.sasquatchAccent, lineWidth: 2)
            )
        }
        .disabled(isGenerating)
    }

    // MARK: - Action

    private func generate() async {
        isGenerating = true
        errorMessage = nil
        do {
            let climbs = try await api.generateClimbs(
                wallId: wallId,
                difficulty: difficulty,
                style: apiStyle
            )
            if climbs.isEmpty {
                errorMessage = "No routes found for this difficulty. Try a different setting."
            } else {
                onGenerated(climbs)
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
            onGenerated: { _ in }
        )
        .environment(APIClient())
    }
}
