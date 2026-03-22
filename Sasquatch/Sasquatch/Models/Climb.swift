import Foundation

struct Climb: Codable, Identifiable {
    let id: Int
    let wallId: Int
    let difficulty: String?
    let classification: String?
    let routeHoldIds: [Int]?
    var isSaved: Bool
    var isFavourite: Bool
    let dateSent: String?
    let climbImgUrl: String?
    let createdAt: String?

    var displayName: String {
        "\((difficulty ?? "unknown").capitalized) \((classification ?? "unknown").capitalized)"
    }

    var isSent: Bool {
        dateSent != nil
    }
}

struct GenerateClimbsRequest: Codable {
    let difficulty: String
    let style: String
    let wingspan: Double?
    let topK: Int?
}
