import SwiftUI

struct SettingsView: View {
    @Environment(APIClient.self) private var api
    @Environment(\.dismiss) private var dismiss

    @State private var username: String = ""
    @State private var heightFeet: Int = 5
    @State private var heightInches: Int = 8
    @State private var isLoading = true
    @State private var isSaving = false

    private let feetRange = 3...8
    private let inchesRange = 0...11

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Button { dismiss() } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(Color.sasquatchText)
                }

                Spacer()

                Text("Settings")
                    .font(.sasquatchHeading(20))
                    .foregroundStyle(Color.sasquatchText)

                Spacer()

                // Invisible spacer to center title
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .hidden()
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 16)

            if isLoading {
                Spacer()
                ProgressView()
                Spacer()
            } else {
                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 24) {
                        // Username field
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Username")
                                .font(.sasquatchBody())
                                .foregroundStyle(Color.sasquatchText)

                            TextField("Enter username", text: $username)
                                .font(.sasquatchRegular(16))
                                .padding(14)
                                .background(.white)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12)
                                        .stroke(Color.sasquatchText.opacity(0.2), lineWidth: 1)
                                )
                        }

                        // Height field
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Height")
                                .font(.sasquatchBody())
                                .foregroundStyle(Color.sasquatchText)

                            HStack(spacing: 12) {
                                // Feet picker
                                HStack(spacing: 4) {
                                    Picker("Feet", selection: $heightFeet) {
                                        ForEach(feetRange, id: \.self) { ft in
                                            Text("\(ft)").tag(ft)
                                        }
                                    }
                                    .pickerStyle(.wheel)
                                    .frame(width: 60, height: 100)
                                    .clipped()

                                    Text("ft")
                                        .font(.sasquatchRegular(16))
                                        .foregroundStyle(Color.sasquatchText)
                                }

                                // Inches picker
                                HStack(spacing: 4) {
                                    Picker("Inches", selection: $heightInches) {
                                        ForEach(inchesRange, id: \.self) { inch in
                                            Text("\(inch)").tag(inch)
                                        }
                                    }
                                    .pickerStyle(.wheel)
                                    .frame(width: 60, height: 100)
                                    .clipped()

                                    Text("in")
                                        .font(.sasquatchRegular(16))
                                        .foregroundStyle(Color.sasquatchText)
                                }
                            }
                            .padding(14)
                            .frame(maxWidth: .infinity, alignment: .center)
                            .background(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .stroke(Color.sasquatchText.opacity(0.2), lineWidth: 1)
                            )
                        }

                        // Save button
                        Button {
                            Task { await save() }
                        } label: {
                            if isSaving {
                                ProgressView()
                                    .tint(.white)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: 50)
                            } else {
                                Text("Save")
                                    .font(.sasquatchButton(16))
                                    .foregroundStyle(.white)
                                    .frame(maxWidth: .infinity)
                                    .frame(height: 50)
                            }
                        }
                        .background(Color.sasquatchSent)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .padding(.top, 8)
                    }
                    .padding(.horizontal, 24)
                    .padding(.top, 16)
                }
            }
        }
        .background(Color.sasquatchBackground)
        .navigationBarHidden(true)
        .task {
            await loadProfile()
        }
    }

    // MARK: - Helpers

    private func heightToCm(feet: Int, inches: Int) -> Double {
        let totalInches = Double(feet * 12 + inches)
        return totalInches * 2.54
    }

    private func cmToFeetInches(_ cm: Double) -> (feet: Int, inches: Int) {
        let totalInches = Int(round(cm / 2.54))
        return (totalInches / 12, totalInches % 12)
    }

    private func loadProfile() async {
        do {
            let profile = try await api.getMe()
            username = profile.username ?? ""
            if let wingspan = profile.wingspan {
                let (ft, inch) = cmToFeetInches(wingspan)
                heightFeet = ft
                heightInches = inch
            }
        } catch {
            print("Failed to load profile: \(error)")
        }
        isLoading = false
    }

    private func save() async {
        isSaving = true
        let wingspan = heightToCm(feet: heightFeet, inches: heightInches)
        do {
            _ = try await api.updateMe(
                username: username.isEmpty ? nil : username,
                wingspan: wingspan
            )
            dismiss()
        } catch {
            print("Failed to save profile: \(error)")
        }
        isSaving = false
    }
}

#Preview {
    NavigationStack {
        SettingsView()
            .environment(APIClient())
    }
}
