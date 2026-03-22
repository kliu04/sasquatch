import Foundation

enum PreviewData {
    static let wall = Wall(
        id: 1,
        name: "North Wall",
        status: .ready,
        wallImgUrl: nil,
        wallPlyUrl: nil,
        holdsImageUrl: nil,
        holdCount: 47,
        errorMessage: nil,
        createdAt: "2026-03-21T12:00:00"
    )

    static let climbs: [Climb] = [
        Climb(
            id: 1, wallId: 1,
            difficulty: "medium", classification: "static",
            routeHoldIds: [3, 12, 7, 22, 31, 45],
            isSaved: true, isFavourite: false,
            dateSent: "2026-03-21T14:00:00",
            climbImgUrl: nil,
            createdAt: "2026-03-21T13:00:00"
        ),
        Climb(
            id: 2, wallId: 1,
            difficulty: "hard", classification: "dynamic",
            routeHoldIds: [1, 5, 14, 28, 40],
            isSaved: true, isFavourite: true,
            dateSent: nil,
            climbImgUrl: nil,
            createdAt: "2026-03-21T13:05:00"
        ),
        Climb(
            id: 3, wallId: 1,
            difficulty: "easy", classification: "static",
            routeHoldIds: [2, 8, 15, 30, 42],
            isSaved: true, isFavourite: false,
            dateSent: "2026-03-21T15:00:00",
            climbImgUrl: nil,
            createdAt: "2026-03-21T13:10:00"
        ),
    ]

    static let wallSummaries: [WallSummary] = [
        WallSummary(id: 1, name: "North Wall", status: .ready, holdCount: 47, wallImgUrl: nil, createdAt: "2026-03-21T12:00:00"),
        WallSummary(id: 2, name: "South Overhang", status: .processing, holdCount: nil, wallImgUrl: nil, createdAt: "2026-03-21T11:00:00"),
        WallSummary(id: 3, name: "Bouldering Cave", status: .ready, holdCount: 32, wallImgUrl: nil, createdAt: "2026-03-20T09:00:00"),
    ]
}
