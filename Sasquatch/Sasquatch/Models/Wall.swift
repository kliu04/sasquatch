import Foundation

struct Wall: Codable, Identifiable {
    let id: Int
    let name: String
    let status: WallStatus
    let wallImgUrl: String?
    let wallPlyUrl: String?
    let holdsImageUrl: String?
    let holdCount: Int?
    let errorMessage: String?
    let createdAt: String

    enum WallStatus: String, Codable {
        case pendingUpload = "pending_upload"
        case processing
        case ready
        case error
    }
}

struct WallSummary: Codable, Identifiable {
    let id: Int
    let name: String
    let status: Wall.WallStatus
    let holdCount: Int?
    let wallImgUrl: String?
    let createdAt: String?
}

struct WallCreateResponse: Codable {
    let id: Int
    let name: String
    let status: String
    let plyUploadUrl: String?
    let pngUploadUrl: String
    let createdAt: String
}
