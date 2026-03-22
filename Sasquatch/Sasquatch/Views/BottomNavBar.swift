import SwiftUI

struct BottomNavBar: View {
    @Binding var selectedTab: Int
    var onHomeTapped: (() -> Void)?
    var onScanTapped: () -> Void

    var body: some View {
        HStack {
            Spacer()

            // Home
            Button { selectedTab = 0; onHomeTapped?() } label: {
                Image(systemName: "house.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(Color.sasquatchTextSecondary)
                    .frame(width: 48, height: 48)
                    .background(.white)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchTextSecondary, lineWidth: 2)
                    )
            }

            Spacer()

            // Scan (center, prominent)
            Button { onScanTapped() } label: {
                Image(systemName: "camera.fill")
                    .font(.system(size: 19))
                    .foregroundStyle(.white)
                    .frame(width: 50, height: 50)
                    .background(Color.sasquatchAccent)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(.white, lineWidth: 2.4)
                    )
                    .shadow(color: .black.opacity(0.2), radius: 5, y: 4)
            }

            Spacer()

            // Walls
            Button { selectedTab = 2 } label: {
                Image(systemName: "square.grid.2x2")
                    .font(.system(size: 20))
                    .foregroundStyle(Color.sasquatchTextSecondary)
                    .frame(width: 48, height: 48)
                    .background(.white)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchTextSecondary, lineWidth: 2)
                    )
            }

            Spacer()
        }
        .padding(.top, 12)
        .padding(.bottom, 12)
        .background(.white)
        .overlay(alignment: .top) {
            Divider()
        }
    }
}
