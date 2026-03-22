import Foundation

struct HoldsResponse: Codable {
    let wallId: Int
    let holds: [Hold]
}

struct Hold: Codable, Identifiable {
    let id: Int
    let position: Position
    let bbox: BBox
    let confidence: Double
    let depth: Double?

    struct Position: Codable {
        let x: Double
        let y: Double
        let z: Double
    }

    struct BBox: Codable {
        let x1: Double
        let y1: Double
        let x2: Double
        let y2: Double
    }
}
