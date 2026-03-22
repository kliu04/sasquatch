import SwiftUI

struct ClimbDetailView: View {
    let climb: Climb
    let wallName: String

    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var currentClimb: Climb
    @State private var showShareSheet = false
    @State private var shareItems: [Any] = []

    init(climb: Climb, wallName: String) {
        self.climb = climb
        self.wallName = wallName
        self._currentClimb = State(initialValue: climb)
    }

    var body: some View {
        ZStack(alignment: .top) {
            Color.sasquatchBackground
                .ignoresSafeArea()

            Color.sasquatchAccent
                .frame(height: 160)
                .ignoresSafeArea(edges: .top)

            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 16) {
                    // Back button
                    Button { dismiss() } label: {
                        Image(systemName: "arrow.left")
                            .font(.system(size: 18, weight: .medium))
                            .foregroundStyle(Color.sasquatchTextSecondary)
                    }
                    .padding(.bottom, -8)

                    // Climb name
                    Text(currentClimb.displayName.uppercased())
                        .font(.system(size: 30, weight: .black))
                        .foregroundStyle(Color.sasquatchTextSecondary)
                        .tracking(-0.6)

                    // Route image
                    routeImage

                    // Tags + SENT badge row
                    tagsRow

                    // Action buttons
                    actionButtons

                    // Send button
                    sendButton
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .background(SharePresenter(isPresented: $showShareSheet, items: shareItems))
    }

    // MARK: - Subviews

    @ViewBuilder
    private var routeImage: some View {
        if let urlStr = currentClimb.climbImgUrl, let url = URL(string: urlStr) {
            CachedAsyncImage(url: url) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(maxWidth: .infinity)
                    .clipped()
            } placeholder: {
                routeImagePlaceholder
            }
            .clipShape(RoundedRectangle(cornerRadius: 16))
        } else {
            routeImagePlaceholder
                .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }

    private var routeImagePlaceholder: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.56, green: 0.72, blue: 0.79).opacity(0.5),
                    Color(red: 0.85, green: 0.65, blue: 0.45).opacity(0.5),
                    Color(red: 0.48, green: 0.56, blue: 0.27).opacity(0.5)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            VStack(spacing: 8) {
                Image(systemName: "point.3.connected.trianglepath.dotted")
                    .font(.system(size: 48))
                Text("Route Preview")
                    .font(.system(size: 14, weight: .semibold))
            }
            .foregroundStyle(.white.opacity(0.8))
        }
        .frame(height: 300)
    }

    private var tagsRow: some View {
        HStack {
            HStack(spacing: 8) {
                TagPill(text: (currentClimb.difficulty ?? "unknown").capitalized)
                TagPill(text: (currentClimb.classification ?? "unknown").capitalized)
            }

            Spacer()

            if currentClimb.isSent {
                Text("SENT!")
                    .font(.system(size: 12, weight: .heavy))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 8)
                    .frame(width: 48, height: 28)
                    .background(Color.sasquatchSent)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
        }
    }

    private var actionButtons: some View {
        HStack(spacing: 8) {
            ActionButton(icon: "bookmark", label: "Save", isActive: currentClimb.isSaved) {
                Task { await toggleSave() }
            }
            ActionButton(icon: "heart", label: "Favorite", isActive: currentClimb.isFavourite) {
                Task { await toggleFavourite() }
            }
            ActionButton(icon: "square.and.arrow.up", label: "Share", isActive: false) {
                Task { await shareClimbImage() }
            }
        }
    }

    private var sendButton: some View {
        Button {
            Task { await markSent() }
        } label: {
            HStack(spacing: 8) {
                Image(systemName: currentClimb.isSent ? "checkmark.circle.fill" : "checkmark.circle")
                    .font(.system(size: 20))
                Text(currentClimb.isSent ? "Sent!" : "Mark as Sent")
                    .font(.system(size: 16, weight: .semibold))
            }
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .frame(height: 56)
            .background(Color.sasquatchSent)
            .clipShape(Capsule())
        }
        .disabled(currentClimb.isSent)
        .opacity(currentClimb.isSent ? 0.7 : 1)
    }

    // MARK: - Actions

    private func toggleSave() async {
        do {
            currentClimb = try await api.updateClimb(
                wallId: currentClimb.wallId,
                climbId: currentClimb.id,
                isSaved: !currentClimb.isSaved
            )
        } catch {
            print("Failed to toggle save: \(error)")
        }
    }

    private func toggleFavourite() async {
        do {
            currentClimb = try await api.updateClimb(
                wallId: currentClimb.wallId,
                climbId: currentClimb.id,
                isFavourite: !currentClimb.isFavourite
            )
        } catch {
            print("Failed to toggle favourite: \(error)")
        }
    }

    private func markSent() async {
        do {
            currentClimb = try await api.markClimbSent(
                wallId: currentClimb.wallId,
                climbId: currentClimb.id
            )
        } catch {
            print("Failed to mark sent: \(error)")
        }
    }

    private func shareClimbImage() async {
        var items: [Any] = ["\(currentClimb.displayName) - Sasquatch"]

        if let urlStr = currentClimb.climbImgUrl, let url = URL(string: urlStr) {
            if let cached = ImageCache.shared.get(url) {
                items.insert(cached, at: 0)
            } else {
                do {
                    let (data, _) = try await URLSession.shared.data(from: url)
                    if let image = UIImage(data: data) {
                        ImageCache.shared.set(image, for: url)
                        items.insert(image, at: 0)
                    }
                } catch {
                    print("Failed to download image for sharing: \(error)")
                }
            }
        }

        shareItems = items
        showShareSheet = true
    }
}

// MARK: - Share Sheet
//
// UIActivityViewController must be PRESENTED modally — it can't be embedded
// inside a SwiftUI .sheet() (which wraps it in another modal, causing a blank
// screen).  This UIViewControllerRepresentable places an invisible host VC in
// the view hierarchy and calls present() directly when isPresented flips to true.

struct SharePresenter: UIViewControllerRepresentable {
    @Binding var isPresented: Bool
    let items: [Any]

    func makeUIViewController(context: Context) -> UIViewController {
        UIViewController()
    }

    func updateUIViewController(_ vc: UIViewController, context: Context) {
        if isPresented && vc.presentedViewController == nil {
            let activity = UIActivityViewController(activityItems: items, applicationActivities: nil)
            activity.completionWithItemsHandler = { _, _, _, _ in
                isPresented = false
            }
            vc.present(activity, animated: true)
        }
    }
}

// MARK: - Tag Pill

struct TagPill: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(Color.sasquatchText)
            .padding(8)
            .background(Color.sasquatchAccent.opacity(0.5))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Action Button

struct ActionButton: View {
    let icon: String
    let label: String
    let isActive: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: isActive ? "\(icon).fill" : icon)
                    .font(.system(size: 16))
                Text(label)
                    .font(.system(size: 14, weight: .semibold))
            }
            .foregroundStyle(Color.sasquatchTextSecondary)
            .frame(maxWidth: .infinity)
            .frame(height: 47)
            .background(.white)
            .clipShape(Capsule())
            .overlay(
                Capsule().stroke(Color.sasquatchTextSecondary, lineWidth: 1)
            )
        }
    }
}

#Preview {
    ClimbDetailView(
        climb: PreviewData.climbs[0],
        wallName: "North Wall"
    )
    .environment(APIClient())
}
