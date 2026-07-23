import Foundation

enum ABIClientError: LocalizedError {
    case invalidServerURL
    case invalidResponse
    case httpStatus(Int, String)
    case malformedEvent

    var errorDescription: String? {
        switch self {
        case .invalidServerURL:
            return "The ABI server URL is invalid."
        case .invalidResponse:
            return "The ABI server returned an invalid response."
        case .httpStatus(let status, let body):
            return "ABI server returned \(status): \(body)"
        case .malformedEvent:
            return "The ABI stream returned malformed data."
        }
    }
}

final class ABIClient {
    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        decoder = JSONDecoder()
        encoder = JSONEncoder()
    }

    func listChats() async throws -> [Chat] {
        try await get("/api/chats?section=chat")
    }

    func createChat(title: String = "New chat") async throws -> Chat {
        try await post(
            "/api/chats",
            body: ChatCreateRequest(title: title, section: "chat", model: nil)
        )
    }

    func listMessages(chatId: String) async throws -> [ChatMessage] {
        try await get("/api/chats/\(chatId)/messages")
    }

    func abort(chatId: String) async throws {
        let _: EmptyResponse = try await post("/api/chats/\(chatId)/abort", body: EmptyBody())
    }

    func streamMessage(chatId: String, text: String) -> AsyncThrowingStream<ChatEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    var request = try makeRequest(path: "/api/chats/\(chatId)/messages")
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    request.httpBody = try encoder.encode(MessageSendRequest(text: text, model: nil))

                    let (bytes, response) = try await session.bytes(for: request)
                    try validate(response: response, body: "")

                    for try await line in bytes.lines {
                        guard line.hasPrefix("data:") else { continue }
                        let payload = String(line.dropFirst(5)).trimmingCharacters(in: .whitespaces)
                        guard !payload.isEmpty else { continue }
                        let event = try Self.decodeEvent(payload)
                        continuation.yield(event)
                        if event == .end {
                            continuation.finish()
                            return
                        }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }

            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        var request = try makeRequest(path: path)
        request.httpMethod = "GET"
        let (data, response) = try await session.data(for: request)
        try validate(response: response, body: String(data: data, encoding: .utf8) ?? "")
        return try decoder.decode(T.self, from: data)
    }

    private func post<Request: Encodable, Response: Decodable>(
        _ path: String,
        body: Request
    ) async throws -> Response {
        var request = try makeRequest(path: path)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        try validate(response: response, body: String(data: data, encoding: .utf8) ?? "")
        return try decoder.decode(Response.self, from: data)
    }

    private func makeRequest(path: String) throws -> URLRequest {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw ABIClientError.invalidServerURL
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 120
        return request
    }

    private func validate(response: URLResponse, body: String) throws {
        guard let http = response as? HTTPURLResponse else {
            throw ABIClientError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            throw ABIClientError.httpStatus(http.statusCode, body)
        }
    }

    private static func decodeEvent(_ payload: String) throws -> ChatEvent {
        guard let data = payload.data(using: .utf8),
              let object = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = object["type"] as? String else {
            throw ABIClientError.malformedEvent
        }

        switch type {
        case "text", "complete":
            return .text(object["text"] as? String ?? "")
        case "error":
            return .error(object["message"] as? String ?? "Unknown ABI stream error")
        case "end":
            return .end
        default:
            return .text("")
        }
    }
}

private struct EmptyBody: Encodable {}
private struct EmptyResponse: Decodable {}

