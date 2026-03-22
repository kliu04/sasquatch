import SwiftUI
import GoogleSignIn

// ⚠️ Configuration
let googleClientID = "379138604067-66fkgehu3knv49ebbe3pc41jv8ogcaih.apps.googleusercontent.com"

// Change to your server IP/hostname for testing. Examples:
//   "http://localhost:8000"          — simulator
//   "http://192.168.1.42:8000"      — device on same WiFi
//   "http://34.11.229.123:8000"     — cloud server
// @wevie try using tailscale so your phone can connect to the mac
let apiBaseURL = "http://206.87.109.14:8000"

@main
struct SasquatchApp: App {
    init() {
        GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: googleClientID)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    GIDSignIn.sharedInstance.handle(url)
                }
        }
    }
}
