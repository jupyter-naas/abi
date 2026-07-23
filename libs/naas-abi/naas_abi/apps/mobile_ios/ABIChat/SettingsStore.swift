import Foundation

@MainActor
final class SettingsStore: ObservableObject {
    @Published var serverURLString: String {
        didSet {
            UserDefaults.standard.set(serverURLString, forKey: Self.serverURLKey)
        }
    }

    private static let serverURLKey = "abi.mobile.serverURL"

    init() {
        serverURLString = UserDefaults.standard.string(forKey: Self.serverURLKey)
            ?? "http://127.0.0.1:55031"
    }

    var serverURL: URL? {
        URL(string: serverURLString.trimmingCharacters(in: .whitespacesAndNewlines))
    }
}

