import SwiftUI
import GoogleSignIn

// ⚠️ Configuration
let googleClientID = "379138604067-66fkgehu3knv49ebbe3pc41jv8ogcaih.apps.googleusercontent.com"

// Change to your server IP/hostname for testing. Examples:
//   "http://localhost:8000"          — simulator
//   "http://192.168.1.42:8000"      — device on same WiFi
//   "http://34.11.229.123:8000"     — cloud server
// @wevie try using tailscale so your phone can connect to the mac
let apiBaseURL = "https://sasquatch-api.randyzhu.com"
//let apiBaseURL = "https://100.114.110.17:8080"

@main
struct SasquatchApp: App {
    init() {
        GIDSignIn.sharedInstance.configuration = GIDConfiguration(clientID: googleClientID)

        // Debug: print available custom font names
        for family in UIFont.familyNames.sorted() {
            let names = UIFont.fontNames(forFamilyName: family)
            if family.contains("Bowlby") || family.contains("Rethink") {
                print("Font family: \(family) -> \(names)")
            }
        }
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
