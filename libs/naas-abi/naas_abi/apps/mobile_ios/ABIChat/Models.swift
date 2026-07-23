import Foundation

struct Chat: Codable, Identifiable, Equatable {
    let id: String
    var title: String
    let section: String
    let model: String?
    let createdAt: Double
    let updatedAt: Double

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case section
        case model
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct ChatMessage: Codable, Identifiable, Equatable {
    let id: String
    let chatId: String
    let role: Role
    var content: String
    let createdAt: Double

    enum Role: String, Codable {
        case user
        case assistant
    }

    enum CodingKeys: String, CodingKey {
        case id
        case chatId = "chat_id"
        case role
        case content
        case createdAt = "created_at"
    }
}

struct StreamingMessage: Identifiable, Equatable {
    let id = "streaming-assistant"
    var content: String
}

enum ChatEvent: Equatable {
    case text(String)
    case error(String)
    case end
}

struct ChatCreateRequest: Encodable {
    let title: String
    let section: String
    let model: String?
}

struct MessageSendRequest: Encodable {
    let text: String
    let model: String?
}

