import SwiftUI

struct SentClimbsView: View {
    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var sentClimbs: [(climb: Climb, wallName: String)] = []
    @State private var isLoading = true

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
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

                        Text("Sent")
                            .font(.sasquatchTitle())
                            .foregroundStyle(Color.sasquatchText)
                    }
                    .padding(.horizontal, 30)
                    .padding(.bottom, 16)
                }

                VStack(alignment: .leading, spacing: 24) {
                    if isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                            .padding(.top, 40)
                    } else if sentClimbs.isEmpty {
                        VStack(spacing: 16) {
                            Image(systemName: "checkmark.circle")
                                .font(.system(size: 48))
                                .foregroundStyle(Color.sasquatchAccent)
                            Text("No sent climbs yet")
                                .font(.sasquatchHeading())
                                .foregroundStyle(Color.sasquatchTextSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                    } else {
                        VStack(spacing: 8) {
                            ForEach(sentClimbs, id: \.climb.id) { item in
                                NavigationLink {
                                    ClimbDetailView(climb: item.climb, wallName: item.wallName)
                                        .environment(api)
                                } label: {
                                    ClimbCard(climb: item.climb)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                .padding(.horizontal, 30)
                .padding(.top, 24)
                .padding(.bottom, 100)
            }
        }
        .background(Color.sasquatchBackground)
        .ignoresSafeArea(edges: .top)
        .navigationBarHidden(true)
        .task { await loadSentClimbs() }
    }

    private func loadSentClimbs() async {
        do {
            let walls = try await api.getWalls()
            var results: [(Climb, String)] = []
            for wall in walls {
                guard let climbs = try? await api.getSavedClimbs(wallId: wall.id) else { continue }
                for climb in climbs where climb.isSent {
                    results.append((climb, wall.name))
                }
            }
            sentClimbs = results.map { (climb: $0.0, wallName: $0.1) }
        } catch {
            print("Failed to load sent climbs: \(error)")
        }
        isLoading = false
    }
}

#Preview {
    NavigationStack {
        SentClimbsView()
            .environment(APIClient())
    }
}
