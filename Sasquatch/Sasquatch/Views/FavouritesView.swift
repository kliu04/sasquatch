import SwiftUI

struct FavouritesView: View {
    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss
    @State private var favourites: [(climb: Climb, wallName: String)] = []
    @State private var isLoading = true

    var body: some View {
        ZStack(alignment: .top) {
            Color.sasquatchBackground
                .ignoresSafeArea()

            Color.sasquatchAccent
                .frame(height: 160)
                .ignoresSafeArea(edges: .top)

            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 24) {
                    Button { dismiss() } label: {
                        Image(systemName: "arrow.left")
                            .font(.system(size: 20, weight: .medium))
                            .foregroundStyle(Color.sasquatchText)
                    }
                    .padding(.top, 4)
                    .padding(.bottom, -16)

                    Text("Favourites")
                        .font(.sasquatchTitle())
                        .foregroundStyle(Color.sasquatchText)

                    if isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                            .padding(.top, 40)
                    } else if favourites.isEmpty {
                        VStack(spacing: 16) {
                            Image(systemName: "heart")
                                .font(.system(size: 48))
                                .foregroundStyle(Color.sasquatchAccent)
                            Text("No favourites yet")
                                .font(.sasquatchHeading())
                                .foregroundStyle(Color.sasquatchTextSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.top, 40)
                    } else {
                        VStack(spacing: 8) {
                            ForEach(favourites, id: \.climb.id) { item in
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
                .padding(.bottom, 40)
            }
        }
        .navigationBarHidden(true)
        .task { await loadFavourites() }
    }

    private func loadFavourites() async {
        do {
            let walls = try await api.getWalls()
            var results: [(Climb, String)] = []
            for wall in walls {
                guard let climbs = try? await api.getSavedClimbs(wallId: wall.id) else { continue }
                for climb in climbs where climb.isFavourite {
                    results.append((climb, wall.name))
                }
            }
            favourites = results.map { (climb: $0.0, wallName: $0.1) }
        } catch {
            print("Failed to load favourites: \(error)")
        }
        isLoading = false
    }
}

#Preview {
    NavigationStack {
        FavouritesView()
            .environment(APIClient())
    }
}
