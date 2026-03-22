import SwiftUI
import ARKit

struct ARViewContainer: UIViewRepresentable {
    var scanManager: ScanManager

    func makeUIView(context: Context) -> ARSCNView {
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

    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}
