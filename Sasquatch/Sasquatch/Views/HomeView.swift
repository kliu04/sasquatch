import SwiftUI
import Charts

struct HomeView: View {
    @Environment(APIClient.self) private var api
    @Environment(AuthManager.self) private var auth
    @Binding var navigationPath: NavigationPath

    @State private var weeklyStats: [(day: String, count: Int)] = []
    @State private var activityEvents: [ActivityEvent] = []

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
        .task(id: api.authToken) {
            guard api.authToken != nil else { return }
            await loadData()
        }
        .onChange(of: navigationPath.count) { _, newCount in
            if newCount == 0 && api.authToken != nil {
                Task { await loadData() }
            }
        }
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
            .chartXAxis {
                AxisMarks { _ in
                    AxisValueLabel()
                        .foregroundStyle(Color.sasquatchTextSecondary)
                }
            }
            .chartYScale(domain: 0...max(weeklyStats.map(\.count).max() ?? 1, 1))
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
        VStack(alignment: .leading, spacing: 12) {
            Text("Activity")
                .font(.system(size: 18, weight: .heavy))
                .foregroundStyle(Color.sasquatchTextSecondary)

            if activityEvents.isEmpty {
                Text("No recent activity")
                    .font(.system(size: 14))
                    .foregroundStyle(.gray)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 16)
            } else {
                VStack(spacing: 0) {
                    ForEach(activityEvents.prefix(5)) { event in
                        HStack(spacing: 12) {
                            Image(systemName: event.icon)
                                .font(.system(size: 14))
                                .foregroundStyle(.white)
                                .frame(width: 28, height: 28)
                                .background(event.color)
                                .clipShape(Circle())

                            VStack(alignment: .leading, spacing: 2) {
                                Text(event.title)
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(Color.sasquatchTextSecondary)
                                Text(event.timeAgo)
                                    .font(.system(size: 11))
                                    .foregroundStyle(.gray)
                            }
                            Spacer()
                        }
                        .padding(.vertical, 8)
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
        await loadStats()
        await loadActivity()
    }

    /// Parse ISO-8601 dates from the API.  The backend stores `DateTime`
    /// **without** timezone (default=datetime.utcnow), so `.isoformat()`
    /// produces naive strings like `"2026-03-22T14:30:00.123456"`.
    /// `ISO8601DateFormatter` with `.withInternetDateTime` **requires** a
    /// timezone designator and silently returns nil for naive strings.
    /// This helper tries every format the API can return.
    private func parseDate(_ string: String) -> Date? {
        // 1. With timezone + fractional seconds  "…+00:00" / "…Z"
        let isoFrac = ISO8601DateFormatter()
        isoFrac.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = isoFrac.date(from: string) { return d }

        // 2. With timezone, no fractional seconds
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime]
        if let d = iso.date(from: string) { return d }

        // 3. Naive datetime WITH fractional seconds (no timezone)
        //    The API stores UTC but omits the timezone designator.
        let df = DateFormatter()
        df.locale = Locale(identifier: "en_US_POSIX")
        df.timeZone = TimeZone(identifier: "UTC")
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        if let d = df.date(from: string) { return d }

        // 4. Naive datetime WITHOUT fractional seconds
        df.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return df.date(from: string)
    }

    private func loadStats() async {
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        let dayFmt = DateFormatter()
        dayFmt.dateFormat = "EEE"

        // Build last 7 days labels
        var days: [(date: Date, label: String)] = []
        for i in (0..<7).reversed() {
            let date = calendar.date(byAdding: .day, value: -i, to: today)!
            days.append((date, dayFmt.string(from: date)))
        }

        // Initialize counts
        var counts = days.map { (day: $0.label, count: 0) }

        do {
            let walls = try await api.getWalls()
            for wall in walls {
                guard let climbs = try? await api.getSavedClimbs(wallId: wall.id) else { continue }
                for climb in climbs where climb.isSent {
                    guard let dateStr = climb.dateSent,
                          let sentDate = parseDate(dateStr) else { continue }
                    let sentDay = calendar.startOfDay(for: sentDate)
                    if let idx = days.firstIndex(where: { calendar.isDate($0.date, inSameDayAs: sentDay) }) {
                        counts[idx].count += 1
                    }
                }
            }
        } catch {
            print("Failed to load stats: \(error)")
        }

        weeklyStats = counts
    }

    private func loadActivity() async {
        var events: [ActivityEvent] = []

        do {
            let walls = try await api.getWalls()

            // Wall creation events
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

            // Climb events (saved + sent)
            for wall in walls {
                guard let climbs = try? await api.getSavedClimbs(wallId: wall.id) else { continue }
                for climb in climbs {
                    if climb.isSaved, let createdAt = climb.createdAt, let date = parseDate(createdAt) {
                        events.append(ActivityEvent(
                            date: date,
                            title: "Saved \(climb.displayName) on \"\(wall.name)\"",
                            icon: "bookmark.fill",
                            color: Color.sasquatchTextSecondary
                        ))
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
            print("Failed to load activity: \(error)")
        }

        activityEvents = events.sorted { $0.date > $1.date }
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
