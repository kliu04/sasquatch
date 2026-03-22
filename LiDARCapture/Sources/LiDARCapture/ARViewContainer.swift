import SwiftUI
import ARKit

public struct ARViewContainer: UIViewRepresentable {
    @ObservedObject var scanManager: ScanManager

    public init(scanManager: ScanManager) {
        self.scanManager = scanManager
    }

    public func makeUIView(context: Context) -> ARSCNView {
        let sceneView = ARSCNView()
        sceneView.automaticallyUpdatesLighting = true

        let configuration = ARWorldTrackingConfiguration()
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth) {
            configuration.frameSemantics.insert(.sceneDepth)
        }
        configuration.environmentTexturing = .automatic

        sceneView.session.run(configuration)
        scanManager.arSession = sceneView.session

        return sceneView
    }

    public func updateUIView(_ uiView: ARSCNView, context: Context) {}
}
