import Foundation

@MainActor
final class ChatViewModel: ObservableObject {
    @Published private(set) var chats: [Chat] = []
    @Published private(set) var selectedChat: Chat?
    @Published private(set) var messages: [ChatMessage] = []
    @Published private(set) var streamingMessage: StreamingMessage?
    @Published private(set) var isLoading = false
    @Published private(set) var isStreaming = false
    @Published var draft = ""
    @Published var errorMessage: String?

    private var client: ABIClient?
    private var streamTask: Task<Void, Never>?

    func configure(serverURL: URL?) {
        guard let serverURL else {
            errorMessage = ABIClientError.invalidServerURL.localizedDescription
            client = nil
            return
        }
        client = ABIClient(baseURL: serverURL)
    }

    func load() async {
        guard let client else { return }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            chats = try await client.listChats()
            if selectedChat == nil {
                selectedChat = chats.first
            }
            if selectedChat == nil {
                selectedChat = try await client.createChat()
                chats = try await client.listChats()
            }
            if let selectedChat {
                messages = try await client.listMessages(chatId: selectedChat.id)
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func select(_ chat: Chat) async {
        guard let client else { return }
        selectedChat = chat
        errorMessage = nil
        do {
            messages = try await client.listMessages(chatId: chat.id)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func createChat() async {
        guard let client else { return }
        errorMessage = nil
        do {
            let chat = try await client.createChat()
            selectedChat = chat
            chats = try await client.listChats()
            messages = []
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func sendDraft() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isStreaming, let selectedChat, let client else { return }

        draft = ""
        errorMessage = nil
        let localUserMessage = ChatMessage(
            id: UUID().uuidString,
            chatId: selectedChat.id,
            role: .user,
            content: text,
            createdAt: Date().timeIntervalSince1970
        )
        messages.append(localUserMessage)
        streamingMessage = StreamingMessage(content: "")
        isStreaming = true

        streamTask = Task { [weak self] in
            do {
                for try await event in client.streamMessage(chatId: selectedChat.id, text: text) {
                    await self?.handle(event, chatId: selectedChat.id)
                }
                await self?.finishStream(chatId: selectedChat.id)
            } catch {
                await MainActor.run {
                    self?.errorMessage = error.localizedDescription
                    self?.isStreaming = false
                }
            }
        }
    }

    func abort() {
        guard let selectedChat, let client else { return }
        streamTask?.cancel()
        streamTask = nil
        isStreaming = false
        Task {
            try? await client.abort(chatId: selectedChat.id)
            await refreshMessages(chatId: selectedChat.id)
        }
    }

    private func handle(_ event: ChatEvent, chatId: String) {
        switch event {
        case .text(let text):
            streamingMessage = StreamingMessage(content: text)
        case .error(let message):
            errorMessage = message
        case .end:
            isStreaming = false
            Task { await refreshMessages(chatId: chatId) }
        }
    }

    private func finishStream(chatId: String) async {
        isStreaming = false
        await refreshMessages(chatId: chatId)
        do {
            chats = try await client?.listChats() ?? chats
            selectedChat = chats.first { $0.id == chatId } ?? selectedChat
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func refreshMessages(chatId: String) async {
        guard let client else { return }
        do {
            messages = try await client.listMessages(chatId: chatId)
            streamingMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

