import SwiftUI
import Charts

struct HomeView: View {
    @Environment(APIClient.self) private var api
    @Environment(AuthManager.self) private var auth
    @Binding var navigationPath: NavigationPath

    // Mock weekly stats data
    private let weeklyStats: [(day: String, count: Int)] = [
        ("Mon", 3), ("Tue", 4), ("Wed", 5),
        ("Thu", 6), ("Fri", 5), ("Sat", 7), ("Sun", 4)
    ]

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 24) {
                // Profile header
                profileHeader

                // Stats card
                statsCard

                // Quick action buttons
                quickActions

                // Activity card
                activityCard
            }
            .padding(.horizontal, 24)
            .padding(.top, 24)
            .padding(.bottom, 100)
        }
        .background(Color.sasquatchBackground)
        .navigationBarHidden(true)
    }

    // MARK: - Subviews

    private var profileHeader: some View {
        HStack(spacing: 16) {
            // Profile image
            Image(systemName: "person.crop.circle.fill")
                .font(.system(size: 50))
                .foregroundStyle(Color.sasquatchTextSecondary.opacity(0.5))
                .frame(width: 80, height: 80)
                .background(.white)
                .clipShape(Circle())
                .overlay(
                    Circle().stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                )

            VStack(alignment: .leading, spacing: 6) {
                Text(auth.userName ?? "Climber")
                    .font(.system(size: 24, weight: .heavy))
                    .foregroundStyle(Color.sasquatchTextSecondary)

                // Tag
                Text("V2 - Fun tag")
                    .font(.system(size: 12))
                    .foregroundStyle(Color.sasquatchTextSecondary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(.white)
                    .clipShape(Capsule())
                    .overlay(
                        Capsule().stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                    )
            }
        }
    }

    private var statsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Stats")
                .font(.system(size: 18, weight: .heavy))
                .foregroundStyle(Color.sasquatchTextSecondary)

            Chart {
                ForEach(weeklyStats, id: \.day) { stat in
                    LineMark(
                        x: .value("Day", stat.day),
                        y: .value("Climbs", stat.count)
                    )
                    .foregroundStyle(Color(red: 0.44, green: 0.75, blue: 0.98))
                    .interpolationMethod(.catmullRom)

                    PointMark(
                        x: .value("Day", stat.day),
                        y: .value("Climbs", stat.count)
                    )
                    .foregroundStyle(Color(red: 0.44, green: 0.75, blue: 0.98))
                    .symbolSize(30)
                }
            }
            .chartYScale(domain: 0...8)
            .chartYAxis {
                AxisMarks(values: [0, 4, 8])
            }
            .frame(height: 120)
        }
        .padding(21)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchTextSecondary.opacity(0.2), lineWidth: 1)
        )
    }

    private var quickActions: some View {
        HStack(spacing: 16) {
            quickActionButton(title: "favs")
            quickActionButton(title: "sent")
        }
    }

    private func quickActionButton(title: String) -> some View {
        Button {
            if title == "favs" { navigationPath.append(HomeDestination.favourites) }
            if title == "sent" { navigationPath.append(HomeDestination.sent) }
        } label: {
            Text(title)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Color.sasquatchTextSecondary)
                .frame(maxWidth: .infinity)
                .frame(height: 80)
                .background(.white)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
                )
        }
    }

    private var activityCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Activity")
                .font(.system(size: 18, weight: .heavy))
                .foregroundStyle(Color.sasquatchTextSecondary)

            RoundedRectangle(cornerRadius: 16)
                .fill(Color.sasquatchBackground)
                .frame(height: 128)
        }
        .padding(21)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchTextSecondary.opacity(0.2), lineWidth: 1)
        )
    }
}

#Preview {
    HomeView(navigationPath: .constant(NavigationPath()))
        .environment(APIClient())
}
