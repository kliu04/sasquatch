import SwiftUI

struct BottomNavBar: View {
    @Binding var selectedTab: Int
    var onTabTapped: (() -> Void)?
    var onScanTapped: () -> Void

    var body: some View {
        HStack {
            // Home
            Button { selectedTab = 0; onTabTapped?() } label: {
                Image(systemName: "house.fill")
                    .font(.system(size: 20))
                    .foregroundStyle(selectedTab == 0 ? .white : Color.sasquatchText)
                    .frame(width: 48, height: 48)
                    .background(selectedTab == 0 ? Color.sasquatchText : .clear)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchText, lineWidth: selectedTab == 0 ? 0 : 1.5)
                    )
            }

            Spacer()

            // Scan (center)
            Button { onScanTapped() } label: {
                Image(systemName: "camera.fill")
                    .font(.system(size: 21))
                    .foregroundStyle(Color.sasquatchText)
                    .frame(width: 48, height: 48)
                    .background(.clear)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchText, lineWidth: 1.5)
                    )
            }

            Spacer()

            // Walls
            Button { selectedTab = 2; onTabTapped?() } label: {
                Image(systemName: "square.grid.2x2")
                    .font(.system(size: 20))
                    .foregroundStyle(selectedTab == 2 ? .white : Color.sasquatchText)
                    .frame(width: 48, height: 48)
                    .background(selectedTab == 2 ? Color.sasquatchText : .clear)
                    .clipShape(Circle())
                    .overlay(
                        Circle().stroke(Color.sasquatchText, lineWidth: selectedTab == 2 ? 0 : 1.5)
                    )
            }
        }
        .padding(.horizontal, 56)
        .padding(.top, 12)
        .padding(.bottom, 12)
        .background(.white)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(Color.sasquatchText.opacity(0.2))
                .frame(height: 1)
        }
    }
}
