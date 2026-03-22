import Foundation
import Observation
import GoogleSignIn

@Observable
class AuthManager {
    var isSignedIn = false
    var userName: String?
    var userEmail: String?
    var authToken: String?

    func signInWithGoogle() async throws {
        guard let windowScene = await UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let rootVC = await windowScene.windows.first?.rootViewController else {
            throw AuthError.noRootViewController
        }

        let result = try await GIDSignIn.sharedInstance.signIn(withPresenting: rootVC)
        let user = result.user
        guard let idToken = user.idToken?.tokenString else {
            throw AuthError.noIdToken
        }

        authToken = idToken
        userName = user.profile?.name
        userEmail = user.profile?.email
        isSignedIn = true
    }

    func restoreSession() async {
        do {
            let user = try await GIDSignIn.sharedInstance.restorePreviousSignIn()
            try await user.refreshTokensIfNeeded()
            guard let idToken = user.idToken?.tokenString else { return }
            authToken = idToken
            userName = user.profile?.name
            userEmail = user.profile?.email
            isSignedIn = true
        } catch {
            // No previous session, stay signed out
        }
    }

    func refreshTokenIfNeeded() async {
        guard let user = GIDSignIn.sharedInstance.currentUser else { return }
        do {
            try await user.refreshTokensIfNeeded()
            authToken = user.idToken?.tokenString
        } catch {
            print("Token refresh failed: \(error)")
        }
    }

    func signInAsDev() {
        authToken = "dev"
        userName = "Dev User"
        userEmail = "dev@sasquatch.local"
        isSignedIn = true
    }

    func signOut() {
        GIDSignIn.sharedInstance.signOut()
        authToken = nil
        userName = nil
        userEmail = nil
        isSignedIn = false
    }
}

enum AuthError: LocalizedError {
    case noRootViewController
    case noIdToken

    var errorDescription: String? {
        switch self {
        case .noRootViewController: return "Unable to find root view controller"
        case .noIdToken: return "Google Sign-In did not return an ID token"
        }
    }
}
