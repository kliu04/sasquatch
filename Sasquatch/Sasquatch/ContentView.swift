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
                        ZStack {
                            HomeView(navigationPath: $navigationPath)
                                .opacity(selectedTab == 0 ? 1 : 0)
                                .allowsHitTesting(selectedTab == 0)
                            WallsListView()
                                .opacity(selectedTab == 0 ? 0 : 1)
                                .allowsHitTesting(selectedTab != 0)
                        }
                        .navigationDestination(isPresented: $showScan) {
                            ScanCaptureView(onScanComplete: { wallId in
                                showScan = false
                                selectedTab = 2
                                navigationPath = NavigationPath()
                                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                    navigationPath.append(WallDestination.detail(wallId))
                                }
                            })
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
                        .navigationDestination(for: WallDestination.self) { dest in
                            switch dest {
                            case .detail(let id):
                                WallDetailView(wallId: id)
                                    .environment(api)
                            }
                        }
                    }

                    if !showScan {
                        BottomNavBar(selectedTab: $selectedTab, onTabTapped: {
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
            api.authManager = auth
            await auth.restoreSession()
            api.authToken = auth.authToken
        }
    }
}

enum HomeDestination: Hashable {
    case favourites
    case sent
}

enum WallDestination: Hashable {
    case detail(Int)
}

#Preview {
    ContentView()
}
