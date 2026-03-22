import SwiftUI

extension Color {
    static let sasquatchBackground = Color(red: 247/255, green: 246/255, blue: 242/255)
    static let sasquatchAccent = Color(red: 143/255, green: 183/255, blue: 201/255)
    static let sasquatchBlue = Color(red: 169/255, green: 199/255, blue: 212/255)
    static let sasquatchText = Color(red: 47/255, green: 47/255, blue: 43/255)
    static let sasquatchTextSecondary = Color(red: 64/255, green: 64/255, blue: 64/255)
    static let sasquatchSent = Color(red: 122/255, green: 143/255, blue: 69/255)
    static let sasquatchFavourite = Color(red: 224/255, green: 160/255, blue: 226/255)
}

extension Font {
    // Bowlby One SC — display titles
    static func sasquatchTitle(_ size: CGFloat = 30) -> Font {
        .custom("BowlbyOneSC-Regular", size: size)
    }

    // Rethink Sans — headings (ExtraBold)
    static func sasquatchHeading(_ size: CGFloat = 20) -> Font {
        .custom("RethinkSans-Regular", size: size, relativeTo: .headline).weight(.heavy)
    }

    // Rethink Sans — body (SemiBold)
    static func sasquatchBody(_ size: CGFloat = 16) -> Font {
        .custom("RethinkSans-Regular", size: size, relativeTo: .body).weight(.semibold)
    }

    // Rethink Sans — buttons (Bold)
    static func sasquatchButton(_ size: CGFloat = 16) -> Font {
        .custom("RethinkSans-Regular", size: size, relativeTo: .body).weight(.bold)
    }

    // Rethink Sans — badges (ExtraBold)
    static func sasquatchBadge(_ size: CGFloat = 12) -> Font {
        .custom("RethinkSans-Regular", size: size, relativeTo: .caption).weight(.heavy)
    }

    // Rethink Sans — regular (semibold as default body weight)
    static func sasquatchRegular(_ size: CGFloat = 14) -> Font {
        .custom("RethinkSans-Regular", size: size, relativeTo: .body).weight(.semibold)
    }

    // Rethink Sans — medium
    static func sasquatchMedium(_ size: CGFloat = 14) -> Font {
        .custom("RethinkSans-Regular", size: size, relativeTo: .body).weight(.medium)
    }
}
