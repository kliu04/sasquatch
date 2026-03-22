import SwiftUI

struct ClimbCard: View {
    let climb: Climb

    var body: some View {
        HStack {
            Text(climb.displayName)
                .font(.sasquatchBody())
                .foregroundStyle(Color.sasquatchTextSecondary)

            Spacer()

            if climb.isSent {
                Text("SENT!")
                    .font(.sasquatchBadge())
                    .foregroundStyle(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sasquatchSent)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
        }
        .padding(.horizontal, 16)
        .frame(height: 73)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.white)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.sasquatchTextSecondary, lineWidth: 1)
        )
    }
}

#Preview {
    VStack(spacing: 8) {
        ClimbCard(climb: PreviewData.climbs[0]) // has SENT!
        ClimbCard(climb: PreviewData.climbs[1]) // no badge
    }
    .padding()
    .background(Color.sasquatchBackground)
}
