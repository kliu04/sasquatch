import SwiftUI
import Charts

struct HomeView: View {
    @Environment(APIClient.self) private var api
    @Environment(AuthManager.self) private var auth
    @Binding var navigationPath: NavigationPath

    @State private var weeklyStats: [(day: String, count: Int)] = []
    @State private var monthlyStats: [(day: String, count: Int)] = []
    @State private var activityEvents: [ActivityEvent] = []
    @State private var recentClimbs: [(climb: Climb, wallName: String)] = []
    @State private var selectedPeriod: StatsPeriod = .weekly

    enum StatsPeriod: String, CaseIterable {
        case weekly = "Weekly"
        case monthly = "Monthly"
    }

    var body: some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 24) {
                // Profile header
                profileHeader

                // Stats card
                statsCard

                // Quick action buttons
                quickActions

                // Recent climbs card
                recentClimbsCard
            }
            .padding(.horizontal, 24)
            .padding(.top, 0)
            .padding(.bottom, 100)
        }
        .background(Color.sasquatchBackground)
        .navigationBarHidden(true)
        .task(id: api.authToken) {
            guard api.authToken != nil else { return }
            await loadData()
        }
    }

    // MARK: - Subviews

    private var profileHeader: some View {
        ZStack(alignment: .topTrailing) {
            HStack(spacing: 14) {
                // Sasquatch mascot avatar
                Image("sasquatch_avatar")
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: 80, height: 80)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchText, lineWidth: 1)
                    )

                VStack(alignment: .leading, spacing: 4) {
                    Text("Sasquatch \u{26F0}\u{FE0F}")
                        .font(.sasquatchTitle(24))
                        .foregroundStyle(Color.sasquatchText)

                    Text("6'7\" | Started climbing January 5, 2026")
                        .font(.sasquatchRegular(12))
                        .foregroundStyle(Color.sasquatchText)
                }

                Spacer()
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 20)
            .frame(maxWidth: .infinity, minHeight: 120)
            .background(
                LinearGradient(
                    colors: [Color.sasquatchBlue.opacity(0.6), Color.sasquatchBlue],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))

            // Settings gear icon
            Image(systemName: "gearshape.fill")
                .font(.system(size: 12))
                .foregroundStyle(Color.sasquatchText)
                .padding(12)
        }
    }

    private var statsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Stats")
                    .font(.sasquatchHeading(18))
                    .foregroundStyle(Color.sasquatchText)

                Spacer()

                // Weekly/Monthly segmented toggle
                HStack(spacing: 0) {
                    ForEach(StatsPeriod.allCases, id: \.self) { period in
                        Text(period.rawValue)
                            .font(.sasquatchRegular(10))
                            .foregroundStyle(selectedPeriod == period ? Color.sasquatchText : Color.sasquatchText.opacity(0.5))
                            .frame(width: 50, height: 21)
                            .background(selectedPeriod == period ? Color.white : Color.clear)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                            .onTapGesture {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    selectedPeriod = period
                                }
                            }
                    }
                }
                .padding(2)
                .background(Color.sasquatchBackground)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            let currentStats = selectedPeriod == .weekly ? weeklyStats : monthlyStats

            Chart {
                ForEach(currentStats, id: \.day) { stat in
                    LineMark(
                        x: .value("Day", stat.day),
                        y: .value("Climbs", stat.count)
                    )
                    .foregroundStyle(Color.sasquatchAccent)
                    .interpolationMethod(.catmullRom)

                    PointMark(
                        x: .value("Day", stat.day),
                        y: .value("Climbs", stat.count)
                    )
                    .foregroundStyle(Color.sasquatchAccent)
                    .symbolSize(30)
                }
            }
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel()
                        .foregroundStyle(Color.sasquatchText)
                        .font(.sasquatchRegular(10))
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [4]))
                        .foregroundStyle(Color.sasquatchText.opacity(0.1))
                    AxisValueLabel()
                        .foregroundStyle(Color.sasquatchText.opacity(0.5))
                        .font(.sasquatchRegular(10))
                }
            }
            .chartYScale(domain: 0...max(currentStats.map(\.count).max() ?? 1, 1))
            .frame(height: 120)
        }
        .padding(21)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchText.opacity(0.2), lineWidth: 1)
        )
        .shadow(color: Color.black.opacity(0.1), radius: 10, x: 0, y: 0)
    }

    private var quickActions: some View {
        HStack(spacing: 10) {
            // Favourite climbs card
            Button {
                navigationPath.append(HomeDestination.favourites)
            } label: {
                ZStack(alignment: .topTrailing) {
                    ZStack(alignment: .bottomLeading) {
                        Color.white

                        Image("sasquatch_favourite")
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(width: 100)
                            .padding(.leading, 4)
                            .padding(.bottom, 4)
                    }

                    VStack(alignment: .trailing, spacing: 0) {
                        Text("Favourite")
                            .font(.sasquatchHeading(24))
                            .foregroundStyle(Color.sasquatchFavourite)
                        Text("climbs")
                            .font(.sasquatchHeading(24))
                            .foregroundStyle(Color.sasquatchText)
                    }
                    .padding(.top, 16)
                    .padding(.trailing, 14)
                }
                .frame(width: 170, height: 170)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.sasquatchText.opacity(0.2), lineWidth: 1)
                )
            }
            .buttonStyle(.plain)

            // Sent climbs card
            Button {
                navigationPath.append(HomeDestination.sent)
            } label: {
                ZStack(alignment: .topTrailing) {
                    ZStack(alignment: .bottomTrailing) {
                        Color.white

                        Image("sasquatch_sent")
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(width: 100)
                            .padding(.trailing, 4)
                            .padding(.bottom, 4)
                    }

                    VStack(alignment: .trailing, spacing: 0) {
                        Text("Sent")
                            .font(.sasquatchHeading(24))
                            .foregroundStyle(Color.sasquatchSent.opacity(0.75))
                        Text("climbs")
                            .font(.sasquatchHeading(24))
                            .foregroundStyle(Color.sasquatchText)
                    }
                    .padding(.top, 16)
                    .padding(.trailing, 14)
                }
                .frame(width: 170, height: 170)
                .clipShape(RoundedRectangle(cornerRadius: 16))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(Color.sasquatchText.opacity(0.2), lineWidth: 1)
                )
            }
            .buttonStyle(.plain)
        }
        .frame(maxWidth: .infinity)
    }

    private var recentClimbsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent climbs")
                .font(.sasquatchHeading(18))
                .foregroundStyle(Color.sasquatchText)

            if recentClimbs.isEmpty {
                Text("No recent climbs")
                    .font(.sasquatchRegular(14))
                    .foregroundStyle(Color.sasquatchText.opacity(0.5))
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 16)
            } else {
                VStack(spacing: 8) {
                    ForEach(recentClimbs.prefix(5), id: \.climb.id) { item in
                        HStack {
                            Text(item.climb.displayName)
                                .font(.sasquatchBody())
                                .foregroundStyle(Color.sasquatchText)

                            Spacer()

                            if item.climb.isSent {
                                Text("SENT!")
                                    .font(.sasquatchBadge())
                                    .foregroundStyle(.white)
                                    .frame(width: 48, height: 28)
                                    .background(Color.sasquatchSent)
                                    .clipShape(RoundedRectangle(cornerRadius: 4))
                            }
                        }
                        .padding(.horizontal, 14)
                        .frame(height: 73)
                        .background(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .overlay(
                            RoundedRectangle(cornerRadius: 16)
                                .stroke(Color.sasquatchText, lineWidth: 1)
                        )
                    }
                }
            }
        }
        .padding(21)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchTextSecondary.opacity(0.2), lineWidth: 1)
        )
    }

    // MARK: - Data

    private func loadData() async {
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        let dayFmt = DateFormatter()
        dayFmt.dateFormat = "EEE"

        // Weekly: last 7 days
        var days: [(date: Date, label: String)] = []
        for i in (0..<7).reversed() {
            let date = calendar.date(byAdding: .day, value: -i, to: today)!
            days.append((date, dayFmt.string(from: date)))
        }
        var counts = days.map { (day: $0.label, count: 0) }

        // Monthly: last 4 weeks
        let weekFmt = DateFormatter()
        weekFmt.dateFormat = "MMM d"
        var weeks: [(date: Date, label: String)] = []
        for i in (0..<4).reversed() {
            let date = calendar.date(byAdding: .weekOfYear, value: -i, to: today)!
            weeks.append((date, weekFmt.string(from: date)))
        }
        var monthlyCounts = weeks.map { (day: $0.label, count: 0) }

        var events: [ActivityEvent] = []
        var allRecentClimbs: [(climb: Climb, wallName: String)] = []

        do {
            let walls = try await api.getWalls()

            for wall in walls {
                if let createdAt = wall.createdAt, let date = parseDate(createdAt) {
                    events.append(ActivityEvent(
                        date: date,
                        title: "Created wall \"\(wall.name)\"",
                        icon: "mountain.2.fill",
                        color: Color.sasquatchAccent
                    ))
                }
            }

            for wall in walls {
                guard let climbs = try? await api.getSavedClimbs(wallId: wall.id) else { continue }
                for climb in climbs {
                    // Weekly stats
                    if climb.isSent, let dateStr = climb.dateSent, let sentDate = parseDate(dateStr) {
                        let sentDay = calendar.startOfDay(for: sentDate)
                        if let idx = days.firstIndex(where: { calendar.isDate($0.date, inSameDayAs: sentDay) }) {
                            counts[idx].count += 1
                        }
                        // Monthly stats
                        for (wIdx, week) in weeks.enumerated() {
                            let weekEnd = wIdx < weeks.count - 1 ? weeks[wIdx + 1].date : calendar.date(byAdding: .day, value: 1, to: today)!
                            if sentDate >= week.date && sentDate < weekEnd {
                                monthlyCounts[wIdx].count += 1
                            }
                        }
                    }

                    // Collect saved climbs for recent section
                    if climb.isSaved {
                        allRecentClimbs.append((climb: climb, wallName: wall.name))

                        if let createdAt = climb.createdAt, let date = parseDate(createdAt) {
                            events.append(ActivityEvent(
                                date: date,
                                title: "Saved \(climb.displayName) on \"\(wall.name)\"",
                                icon: "bookmark.fill",
                                color: Color.sasquatchTextSecondary
                            ))
                        }
                    }
                    if let dateStr = climb.dateSent, let date = parseDate(dateStr) {
                        events.append(ActivityEvent(
                            date: date,
                            title: "Sent \(climb.displayName) on \"\(wall.name)\"",
                            icon: "checkmark.circle.fill",
                            color: Color.sasquatchSent
                        ))
                    }
                }
            }
        } catch {
            print("Failed to load home data: \(error)")
        }

        weeklyStats = counts
        monthlyStats = monthlyCounts
        activityEvents = events.sorted { $0.date > $1.date }

        // Sort recent climbs by createdAt descending
        recentClimbs = allRecentClimbs.sorted { a, b in
            guard let aDate = a.climb.createdAt.flatMap({ parseDate($0) }),
                  let bDate = b.climb.createdAt.flatMap({ parseDate($0) }) else {
                return false
            }
            return aDate > bDate
        }
    }

    private func parseDate(_ string: String) -> Date? {
        let isoFrac = ISO8601DateFormatter()
        isoFrac.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = isoFrac.date(from: string) { return d }

        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        if let d = iso.date(from: string) { return d }

        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(identifier: "UTC")
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let d = df.date(from: string) { return d }

        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return df.date(from: string)
    }
}

// MARK: - Activity Event

struct ActivityEvent: Identifiable {
    let id = UUID()
    let date: Date
    let title: String
    let icon: String
    let color: Color

    var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}

#Preview {
    HomeView(navigationPath: .constant(NavigationPath()))
        .environment(APIClient())
}
