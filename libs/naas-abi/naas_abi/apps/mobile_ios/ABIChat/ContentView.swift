import SwiftUI

struct ContentView: View {
    @EnvironmentObject private var settings: SettingsStore
    @StateObject private var viewModel = ChatViewModel()
    @State private var showingSettings = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if let error = viewModel.errorMessage {
                    ErrorBanner(message: error)
                }

                MessageList(
                    messages: viewModel.messages,
                    streamingMessage: viewModel.streamingMessage
                )

                Composer(
                    draft: $viewModel.draft,
                    isStreaming: viewModel.isStreaming,
                    send: viewModel.sendDraft,
                    abort: viewModel.abort
                )
            }
            .navigationTitle(viewModel.selectedChat?.title ?? "ABI")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Button("New Chat") {
                            Task { await viewModel.createChat() }
                        }
                        Divider()
                        ForEach(viewModel.chats) { chat in
                            Button(chat.title) {
                                Task { await viewModel.select(chat) }
                            }
                        }
                    } label: {
                        Image(systemName: "sidebar.left")
                    }
                }

                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingSettings = true
                    } label: {
                        Image(systemName: "gearshape")
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                SettingsView(serverURLString: $settings.serverURLString) {
                    viewModel.configure(serverURL: settings.serverURL)
                    Task { await viewModel.load() }
                }
            }
            .task {
                viewModel.configure(serverURL: settings.serverURL)
                await viewModel.load()
            }
            .refreshable {
                await viewModel.load()
            }
        }
    }
}

private struct MessageList: View {
    let messages: [ChatMessage]
    let streamingMessage: StreamingMessage?

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(messages) { message in
                        MessageBubble(role: message.role, text: message.content)
                            .id(message.id)
                    }
                    if let streamingMessage {
                        MessageBubble(role: .assistant, text: streamingMessage.content)
                            .id(streamingMessage.id)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .background(Color(.systemGroupedBackground))
            .onChange(of: messages.count) { _ in
                scrollToBottom(proxy: proxy)
            }
            .onChange(of: streamingMessage?.content) { _ in
                scrollToBottom(proxy: proxy)
            }
        }
    }

    private func scrollToBottom(proxy: ScrollViewProxy) {
        let target = streamingMessage?.id ?? messages.last?.id
        guard let target else { return }
        withAnimation(.easeOut(duration: 0.2)) {
            proxy.scrollTo(target, anchor: .bottom)
        }
    }
}

private struct MessageBubble: View {
    let role: ChatMessage.Role
    let text: String

    var body: some View {
        HStack {
            if role == .user { Spacer(minLength: 48) }
            Text(text.isEmpty ? "..." : text)
                .font(.body)
                .textSelection(.enabled)
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .foregroundStyle(role == .user ? .white : .primary)
                .background(role == .user ? Color.accentColor : Color(.secondarySystemGroupedBackground))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            if role == .assistant { Spacer(minLength: 48) }
        }
    }
}

private struct Composer: View {
    @Binding var draft: String
    let isStreaming: Bool
    let send: () -> Void
    let abort: () -> Void

    var body: some View {
        HStack(alignment: .bottom, spacing: 10) {
            TextField("Message ABI", text: $draft, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...6)
                .padding(.horizontal, 12)
                .padding(.vertical, 10)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))

            Button {
                isStreaming ? abort() : send()
            } label: {
                Image(systemName: isStreaming ? "stop.fill" : "arrow.up")
                    .font(.system(size: 16, weight: .semibold))
                    .frame(width: 36, height: 36)
                    .foregroundStyle(.white)
                    .background(isStreaming ? Color.red : Color.accentColor)
                    .clipShape(Circle())
            }
            .disabled(!isStreaming && draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .padding(.horizontal, 12)
        .padding(.top, 10)
        .padding(.bottom, 12)
        .background(.regularMaterial)
    }
}

private struct ErrorBanner: View {
    let message: String

    var body: some View {
        Text(message)
            .font(.footnote)
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(Color.red)
    }
}

private struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @Binding var serverURLString: String
    let onSave: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("ABI server") {
                    TextField("Server URL", text: $serverURLString)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
                        .autocorrectionDisabled()
                }
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave()
                        dismiss()
                    }
                }
            }
        }
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
            .environmentObject(SettingsStore())
    }
}
