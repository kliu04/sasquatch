import SwiftUI
import GoogleSignInSwift

struct SignInView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(APIClient.self) private var api
    @State private var isSigningIn = false
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            Color.sasquatchBackground
                .ignoresSafeArea()

            VStack(spacing: 40) {
                Spacer()

                // Logo area
                VStack(spacing: 16) {
                    Image(systemName: "mountain.2.fill")
                        .font(.system(size: 64))
                        .foregroundStyle(Color.sasquatchAccent)

                    Text("SASQUATCH")
                        .font(.system(size: 36, weight: .black))
                        .foregroundStyle(Color.sasquatchText)

                    Text("Climb smarter with AI route generation")
                        .font(.system(size: 14))
                        .foregroundStyle(Color.sasquatchTextSecondary)
                }

                Spacer()

                // Sign in area
                VStack(spacing: 16) {
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.system(size: 13))
                            .foregroundStyle(.red)
                            .multilineTextAlignment(.center)
                    }

                    // Google Sign-In button
                    Button {
                        Task { await signIn() }
                    } label: {
                        HStack(spacing: 12) {
                            if isSigningIn {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "g.circle.fill")
                                    .font(.system(size: 22))
                            }
                            Text(isSigningIn ? "Signing in..." : "Sign in with Google")
                                .font(.system(size: 16, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .frame(height: 52)
                        .foregroundStyle(.white)
                        .background(Color.sasquatchTextSecondary)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                    }
                    .disabled(isSigningIn)

                    // Dev login
                    Button {
                        auth.signInAsDev()
                        api.authToken = auth.authToken
                    } label: {
                        HStack(spacing: 8) {
                            Image(systemName: "hammer.fill")
                                .font(.system(size: 16))
                            Text("Continue as Dev")
                                .font(.system(size: 14, weight: .medium))
                        }
                        .frame(maxWidth: .infinity)
                        .frame(height: 44)
                        .foregroundStyle(Color.sasquatchTextSecondary)
                        .background(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                        )
                    }
                }
                .padding(.horizontal, 30)
                .padding(.bottom, 60)
            }
        }
    }

    private func signIn() async {
        isSigningIn = true
        errorMessage = nil
        do {
            try await auth.signInWithGoogle()
            api.authToken = auth.authToken
        } catch {
            errorMessage = error.localizedDescription
        }
        isSigningIn = false
    }
}

#Preview {
    SignInView()
        .environment(AuthManager())
        .environment(APIClient())
}
