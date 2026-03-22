import SwiftUI

struct ContentView: View {
    @State private var api = APIClient()
    @State private var auth = AuthManager()
    @State private var selectedTab = 0
    @State private var showScan = false
    @State private var navigationPath = NavigationPath()

    var body: some View {
        Group {
            if auth.isSignedIn {
                ZStack(alignment: .bottom) {
                    NavigationStack(path: $navigationPath) {
                        Group {
                            switch selectedTab {
                            case 0:
                                HomeView(navigationPath: $navigationPath)
                            default:
                                WallsListView()
                            }
                        }
                        .navigationDestination(isPresented: $showScan) {
                            ScanCaptureView()
                        }
                        .navigationDestination(for: HomeDestination.self) { dest in
                            switch dest {
                            case .favourites:
                                FavouritesView()
                                    .environment(api)
                            case .sent:
                                SentClimbsView()
                                    .environment(api)
                            }
                        }
                    }

                    if !showScan {
                        BottomNavBar(selectedTab: $selectedTab, onHomeTapped: {
                            navigationPath = NavigationPath()
                        }) {
                            showScan = true
                        }
                    }
                }
                .ignoresSafeArea(.keyboard)
                .onChange(of: selectedTab) {
                    navigationPath = NavigationPath()
                }
            } else {
                SignInView()
            }
        }
        .environment(api)
        .environment(auth)
        .task {
            api.baseURL = apiBaseURL
            await auth.restoreSession()
            api.authToken = auth.authToken
        }
    }
}

enum HomeDestination: Hashable {
    case favourites
    case sent
}

#Preview {
    ContentView()
}
