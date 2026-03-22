import SwiftUI
import UIKit

/// Drop-in replacement for AsyncImage that caches downloaded images in memory.
struct CachedAsyncImage<Content: View, Placeholder: View>: View {
    let url: URL?
    @ViewBuilder let content: (Image) -> Content
    @ViewBuilder let placeholder: () -> Placeholder

    @State private var image: UIImage?

    var body: some View {
        if let image {
            content(Image(uiImage: image))
        } else {
            placeholder()
                .task(id: url) {
                    guard let url else { return }
                    if let cached = ImageCache.shared.get(url) {
                        image = cached
                        return
                    }
                    do {
                        let (data, _) = try await URLSession.shared.data(from: url)
                        guard !Task.isCancelled else { return }
                        if let downloaded = UIImage(data: data) {
                            ImageCache.shared.set(downloaded, for: url)
                            image = downloaded
                        }
                    } catch {
                        // stay on placeholder
                    }
                }
        }
    }
}

/// Simple in-memory image cache using NSCache (auto-evicts under memory pressure).
final class ImageCache: @unchecked Sendable {
    static let shared = ImageCache()
    private let cache = NSCache<NSURL, UIImage>()

    private init() {
        cache.countLimit = 100
    }

    func get(_ url: URL) -> UIImage? {
        cache.object(forKey: url as NSURL)
    }

    func set(_ image: UIImage, for url: URL) {
        cache.setObject(image, forKey: url as NSURL)
    }
}
