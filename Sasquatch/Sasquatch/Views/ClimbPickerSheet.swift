import SwiftUI

struct ClimbPickerSheet: View {
    let climbs: [Climb]
    let wallId: Int
    var onSave: () -> Void
    var onDismiss: () -> Void

    @Environment(APIClient.self) private var api
    @State private var selectedIndex = 0
    @State private var currentClimbs: [Climb]
    @State private var showShareSheet = false
    @State private var shareItems: [Any] = []

    init(climbs: [Climb], wallId: Int, onSave: @escaping () -> Void, onDismiss: @escaping () -> Void) {
        self.climbs = climbs
        self.wallId = wallId
        self.onSave = onSave
        self.onDismiss = onDismiss
        self._currentClimbs = State(initialValue: climbs)
    }

    private var currentClimb: Climb { currentClimbs[selectedIndex] }

    var body: some View {
        VStack(spacing: 16) {
            // Climb image
            if let urlStr = currentClimb.climbImgUrl, let url = URL(string: urlStr) {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(maxWidth: .infinity, maxHeight: 240)
                    default:
                        imagePlaceholder
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                imagePlaceholder
            }

            // Tags
            HStack(spacing: 8) {
                TagPill(text: (currentClimb.difficulty ?? "unknown").capitalized)
                TagPill(text: (currentClimb.classification ?? "unknown").capitalized)
                Spacer()
            }

            // Route selector
            if climbs.count > 1 {
                climbSelector
            }

            // Action buttons
            HStack(spacing: 8) {
                ActionButton(icon: "bookmark", label: "Save", isActive: currentClimb.isSaved) {
                    Task { await toggleSave() }
                }
                ActionButton(icon: "heart", label: "Favorite", isActive: currentClimb.isFavourite) {
                    Task { await toggleFavourite() }
                }
                ActionButton(icon: "square.and.arrow.up", label: "Share", isActive: false) {
                    Task { await shareClimb() }
                }
            }

            // Done button
            Button { onSave() } label: {
                Text("Done")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 48)
                    .background(Color.sasquatchTextSecondary)
                    .clipShape(Capsule())
            }
        }
        .padding(16)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 24))
        .padding(.horizontal, 24)
        .sheet(isPresented: $showShareSheet) {
            ShareSheet(items: shareItems)
        }
    }

    private var imagePlaceholder: some View {
        RoundedRectangle(cornerRadius: 8)
            .fill(Color.sasquatchBackground)
            .frame(height: 200)
            .overlay {
                Image(systemName: "figure.climbing")
                    .font(.system(size: 40))
                    .foregroundStyle(.gray.opacity(0.5))
            }
    }

    private var climbSelector: some View {
        HStack(spacing: 4) {
            ForEach(climbs.indices, id: \.self) { index in
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        selectedIndex = index
                    }
                } label: {
                    Text("Route \(index + 1)")
                        .font(.system(size: 13, weight: selectedIndex == index ? .bold : .medium))
                        .foregroundStyle(Color.sasquatchTextSecondary)
                        .frame(maxWidth: .infinity)
                        .frame(height: 28)
                        .background(
                            selectedIndex == index
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

    // MARK: - Actions

    private func toggleSave() async {
        do {
            currentClimbs[selectedIndex] = try await api.updateClimb(
                wallId: wallId, climbId: currentClimb.id,
                isSaved: !currentClimb.isSaved
            )
        } catch {
            print("Failed to toggle save: \(error)")
        }
    }

    private func toggleFavourite() async {
        do {
            currentClimbs[selectedIndex] = try await api.updateClimb(
                wallId: wallId, climbId: currentClimb.id,
                isFavourite: !currentClimb.isFavourite
            )
        } catch {
            print("Failed to toggle favourite: \(error)")
        }
    }

    private func shareClimb() async {
        var items: [Any] = ["\(currentClimb.displayName) - Sasquatch"]
        if let urlStr = currentClimb.climbImgUrl, let url = URL(string: urlStr) {
            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                if let image = UIImage(data: data) {
                    items.insert(image, at: 0)
                }
            } catch {
                print("Failed to download image for sharing: \(error)")
            }
        }
        shareItems = items
        showShareSheet = true
    }
}
