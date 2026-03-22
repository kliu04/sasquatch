import SwiftUI

extension Color {
    // Figma design tokens
    static let sasquatchBackground = Color(red: 247/255, green: 246/255, blue: 242/255)
    static let sasquatchAccent = Color(red: 143/255, green: 183/255, blue: 201/255)
    static let sasquatchText = Color(red: 47/255, green: 47/255, blue: 43/255)
    static let sasquatchTextSecondary = Color(red: 64/255, green: 64/255, blue: 64/255)
    static let sasquatchSent = Color(red: 122/255, green: 143/255, blue: 69/255)
}

extension Font {
    static func sasquatchTitle() -> Font {
        .system(size: 30, weight: .black, design: .default)
    }

    static func sasquatchHeading() -> Font {
        .system(size: 20, weight: .heavy)
    }

    static func sasquatchBody() -> Font {
        .system(size: 16, weight: .semibold)
    }

    static func sasquatchButton() -> Font {
        .system(size: 16, weight: .bold)
    }

    static func sasquatchBadge() -> Font {
        .system(size: 12, weight: .heavy)
    }
}
