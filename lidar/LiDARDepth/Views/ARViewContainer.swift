import SwiftUI
import ARKit

struct ARViewContainer: UIViewRepresentable {
    @ObservedObject var scanManager: ScanManager

    func makeUIView(context: Context) -> ARSCNView {
        let sceneView = ARSCNView()
        sceneView.automaticallyUpdatesLighting = true

        let configuration = ARWorldTrackingConfiguration()
        if ARWorldTrackingConfiguration.supportsSceneReconstruction(.mesh) {
            configuration.sceneReconstruction = .mesh
        }
        configuration.environmentTexturing = .automatic

        sceneView.session.run(configuration)
        scanManager.arSession = sceneView.session

        return sceneView
    }

    func updateUIView(_ uiView: ARSCNView, context: Context) {}
}
