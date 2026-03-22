import SwiftUI

struct ContentView: View {
    @State private var api = APIClient()
    @State private var auth = AuthManager()
    @State private var selectedTab = 0
    @State private var showScan = false

    var body: some View {
        Group {
            if auth.isSignedIn {
                ZStack(alignment: .bottom) {
                    NavigationStack {
                        Group {
                            switch selectedTab {
                            case 0:
                                HomeView()
                            default:
                                WallsListView()
                            }
                        }
                        .navigationDestination(isPresented: $showScan) {
                            ScanCaptureView()
                        }
                    }

                    if !showScan {
                        BottomNavBar(selectedTab: $selectedTab) {
                            showScan = true
                        }
                    }
                }
                .ignoresSafeArea(.keyboard)
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

#Preview {
    ContentView()
}
