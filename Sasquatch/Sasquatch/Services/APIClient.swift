import Foundation
import Observation

@Observable
class APIClient {
    var baseURL = "http://localhost:8000"
    var authToken: String?
    var authManager: AuthManager?

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }()

    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.keyEncodingStrategy = .convertToSnakeCase
        return e
    }()

    // MARK: - Generic Request

    private func request(_ path: String, method: String = "GET", body: (any Encodable)? = nil) async throws -> Data {
        // Refresh token if we have an auth manager
        if let authManager {
            await authManager.refreshTokenIfNeeded()
            authToken = authManager.authToken
        }

        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw URLError(.badURL)
        }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            req.httpBody = try encoder.encode(AnyEncodable(body))
        }
        let (data, response) = try await URLSession.shared.data(for: req)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw APIError.httpError(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return data
    }

    // MARK: - Walls

    func getWalls() async throws -> [WallSummary] {
        let data = try await request("/walls")
        return try decoder.decode([WallSummary].self, from: data)
    }

    func getWall(_ id: Int, poll: Bool = false, timeout: Int = 30) async throws -> Wall {
        var path = "/walls/\(id)"
        if poll { path += "?poll=true&timeout=\(timeout)" }
        let data = try await request(path)
        return try decoder.decode(Wall.self, from: data)
    }

    func createWall(name: String, hasPly: Bool = true) async throws -> WallCreateResponse {
        let body = CreateWallRequest(name: name, hasPly: hasPly)
        let data = try await request("/walls", method: "POST", body: body)
        return try decoder.decode(WallCreateResponse.self, from: data)
    }

    func triggerProcessing(wallId: Int) async throws {
        _ = try await request("/walls/\(wallId)/process", method: "POST")
    }

    func updateWall(_ id: Int, name: String) async throws -> Wall {
        let body = ["name": name]
        let data = try await request("/walls/\(id)", method: "PATCH", body: body)
        return try decoder.decode(Wall.self, from: data)
    }

    func deleteWall(_ id: Int) async throws {
        _ = try await request("/walls/\(id)", method: "DELETE")
    }

    // MARK: - Holds

    func getHolds(wallId: Int) async throws -> HoldsResponse {
        let data = try await request("/walls/\(wallId)/holds")
        return try decoder.decode(HoldsResponse.self, from: data)
    }

    // MARK: - Climbs

    func getSavedClimbs(wallId: Int) async throws -> [Climb] {
        let data = try await request("/walls/\(wallId)/climbs")
        return try decoder.decode([Climb].self, from: data)
    }

    func generateClimbs(wallId: Int, difficulty: String, style: String, wingspan: Double? = nil, topK: Int? = nil) async throws -> [Climb] {
        let body = GenerateClimbsRequest(difficulty: difficulty, style: style, wingspan: wingspan, topK: topK)
        let data = try await request("/walls/\(wallId)/climbs", method: "POST", body: body)
        return try decoder.decode([Climb].self, from: data)
    }

    func updateClimb(wallId: Int, climbId: Int, isSaved: Bool? = nil, isFavourite: Bool? = nil) async throws -> Climb {
        var body: [String: Bool] = [:]
        if let isSaved { body["is_saved"] = isSaved }
        if let isFavourite { body["is_favourite"] = isFavourite }
        let data = try await request("/walls/\(wallId)/climbs/\(climbId)", method: "PATCH", body: body)
        return try decoder.decode(Climb.self, from: data)
    }

    func markClimbSent(wallId: Int, climbId: Int) async throws -> Climb {
        let data = try await request("/walls/\(wallId)/climbs/\(climbId)/sent", method: "PATCH")
        return try decoder.decode(Climb.self, from: data)
    }

    // MARK: - User Profile

    func getMe() async throws -> UserProfile {
        let data = try await request("/users/me")
        return try decoder.decode(UserProfile.self, from: data)
    }

    func updateMe(username: String? = nil, wingspan: Double? = nil) async throws -> UserProfile {
        var body: [String: AnyEncodable] = [:]
        if let username { body["username"] = AnyEncodable(username) }
        if let wingspan { body["wingspan"] = AnyEncodable(wingspan) }
        let data = try await request("/users/me", method: "PATCH", body: body)
        return try decoder.decode(UserProfile.self, from: data)
    }

    // MARK: - Upload

    func uploadFile(to signedURL: String, data fileData: Data, contentType: String) async throws {
        guard let url = URL(string: signedURL) else { throw URLError(.badURL) }
        var req = URLRequest(url: url)
        req.httpMethod = "PUT"
        req.setValue(contentType, forHTTPHeaderField: "Content-Type")
        req.httpBody = fileData
        let (_, response) = try await URLSession.shared.data(for: req)
        if let http = response as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw APIError.httpError(http.statusCode, "Upload failed")
        }
    }
}

// MARK: - Helpers

enum APIError: LocalizedError {
    case httpError(Int, String)

    var errorDescription: String? {
        switch self {
        case .httpError(let code, let message):
            return "HTTP \(code): \(message)"
        }
    }
}

private struct CreateWallRequest: Encodable {
    let name: String
    let hasPly: Bool
}

struct AnyEncodable: Encodable {
    let value: any Encodable
    init(_ value: any Encodable) { self.value = value }
    func encode(to encoder: Encoder) throws {
        try value.encode(to: encoder)
    }
}
