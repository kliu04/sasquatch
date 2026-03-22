import SwiftUI

struct ClimbDetailView: View {
    let climb: Climb
    let wallName: String

    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var currentClimb: Climb
    @State private var showShareSheet = false
    @State private var shareItems: [Any] = []
    @State private var showDeleteConfirmation = false

    init(climb: Climb, wallName: String) {
        self.climb = climb
        self.wallName = wallName
        self._currentClimb = State(initialValue: climb)
    }

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                // Blue header with back button and climb name
                ZStack(alignment: .bottomLeading) {
                    Color.sasquatchBlue
                        .frame(height: 160)

                    VStack(alignment: .leading, spacing: 8) {
                        Button { dismiss() } label: {
                            Image(systemName: "arrow.left")
                                .font(.system(size: 20, weight: .medium))
                                .foregroundStyle(Color.sasquatchText)
                                .frame(width: 44, height: 44)
                                .contentShape(Rectangle())
                        }

                        Text(currentClimb.displayName.uppercased())
                            .font(.sasquatchTitle(24))
                            .foregroundStyle(Color.sasquatchText)
                    }
                    .padding(.horizontal, 24)
                    .padding(.bottom, 16)
                }

                // Content
                VStack(alignment: .leading, spacing: 16) {
                    routeImage
                    tagsRow
                    actionButtons
                    sendButton
                }
                .padding(.horizontal, 24)
                .padding(.top, 20)
                .padding(.bottom, 100)
            }
        }
        .background(Color.sasquatchBackground)
        .ignoresSafeArea(edges: .top)
        .navigationBarHidden(true)
        .background(SharePresenter(isPresented: $showShareSheet, items: shareItems))
        .overlay {
            if showDeleteConfirmation {
                deleteConfirmationModal
            }
        }
        .animation(.easeInOut(duration: 0.2), value: showDeleteConfirmation)
    }

    // MARK: - Delete Confirmation

    private var deleteConfirmationModal: some View {
        ZStack {
            Color.black.opacity(0.5)
                .ignoresSafeArea()
                .onTapGesture { showDeleteConfirmation = false }

            VStack(spacing: 24) {
                Text("Delete climb?")
                    .font(.sasquatchTitle(20))
                    .foregroundStyle(Color.sasquatchText)

                HStack(spacing: 12) {
                    Button {
                        showDeleteConfirmation = false
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "xmark")
                                .font(.system(size: 14, weight: .semibold))
                            Text("Cancel")
                                .font(.sasquatchBody(16))
                        }
                        .foregroundStyle(Color.sasquatchText)
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                        .background(.white)
                        .clipShape(Capsule())
                        .overlay(Capsule().stroke(Color.sasquatchText, lineWidth: 1))
                    }

                    Button {
                        Task { await deleteClimb() }
                    } label: {
                        HStack(spacing: 6) {
                            Image(systemName: "trash")
                                .font(.system(size: 14))
                            Text("Delete")
                                .font(.sasquatchButton(16))
                        }
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                        .background(Color.red)
                        .clipShape(Capsule())
                    }
                }
            }
            .padding(24)
            .background(.white)
            .clipShape(RoundedRectangle(cornerRadius: 24))
            .padding(.horizontal, 40)
        }
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
            ActionButton(icon: "bookmark", label: "Save", isActive: currentClimb.isSaved, activeColor: Color.sasquatchSent) {
                Task { await toggleSave() }
            }
            ActionButton(icon: "heart", label: "Favorite", isActive: currentClimb.isFavourite, activeColor: Color.sasquatchFavourite) {
                Task { await toggleFavourite() }
            }
            ActionButton(icon: "square.and.arrow.up", label: "Share", isActive: false) {
                Task { await shareClimbImage() }
            }
            // Delete button
            Button {
                showDeleteConfirmation = true
            } label: {
                Image(systemName: "trash")
                    .font(.system(size: 16))
                    .foregroundStyle(Color.sasquatchTextSecondary)
                    .frame(width: 47, height: 47)
                    .background(.white)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                    )
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

    private func deleteClimb() async {
        do {
            try await api.deleteClimb(wallId: currentClimb.wallId, climbId: currentClimb.id)
            showDeleteConfirmation = false
            dismiss()
        } catch {
            print("Failed to delete climb: \(error)")
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
    var activeColor: Color = Color.sasquatchTextSecondary
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: isActive ? "\(icon).fill" : icon)
                    .font(.system(size: 16))
                Text(isActive && label == "Save" ? "Saved" : label)
                    .font(.system(size: 14, weight: .semibold))
            }
            .foregroundStyle(isActive ? .white : Color.sasquatchTextSecondary)
            .frame(maxWidth: .infinity)
            .frame(height: 47)
            .background(isActive ? activeColor : .white)
            .clipShape(Capsule())
            .overlay(
                isActive ? nil : Capsule().stroke(Color.sasquatchTextSecondary, lineWidth: 1)
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
