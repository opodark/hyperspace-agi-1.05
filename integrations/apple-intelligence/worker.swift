// SPDX-License-Identifier: Apache-2.0
import Foundation
import FoundationModels

struct Input: Decodable {
    let prompt: String
    let instructions: String
    let max_tokens: Int
}

func emit(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]) {
        FileHandle.standardOutput.write(data)
        FileHandle.standardOutput.write(Data("\n".utf8))
    }
}

@main
struct AppleWorker {
    static func main() async {
        let model = SystemLanguageModel.default
        let availability = model.availability
        let ready = availability == .available
        if CommandLine.arguments.contains("--check") {
            emit(["ok": ready, "availability": String(describing: availability),
                  "backend": "apple-foundation-models", "execution": "on-device"])
            return
        }
        guard ready else {
            emit(["ok": false, "error": "model_unavailable",
                  "availability": String(describing: availability)])
            return
        }
        do {
            let data = FileHandle.standardInput.readDataToEndOfFile()
            guard data.count <= 65536 else {
                emit(["ok": false, "error": "input_too_large"])
                return
            }
            let input = try JSONDecoder().decode(Input.self, from: data)
            guard !input.prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
                  (1...1024).contains(input.max_tokens) else {
                emit(["ok": false, "error": "invalid_input"])
                return
            }
            let session = LanguageModelSession(model: model, instructions: input.instructions)
            let response = try await session.respond(
                to: input.prompt,
                options: GenerationOptions(maximumResponseTokens: input.max_tokens))
            emit(["ok": true, "text": response.content,
                  "backend": "apple-foundation-models", "execution": "on-device"])
        } catch {
            // Keep native errors visible, including guardrails/context exhaustion.
            // No prompt logging and no fallback to a cloud model.
            emit(["ok": false, "error": "generation_failed",
                  "detail": String(describing: error)])
        }
    }
}
