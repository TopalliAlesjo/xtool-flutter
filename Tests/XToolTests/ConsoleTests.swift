import Foundation
import NIOCore
import Testing
import XKit
@testable import XToolSupport

@Test func promptFailsOnClosedInput() async {
    let input = AsyncStream<ByteBuffer> { $0.finish() }
    await #expect(throws: Console.Error.self) {
        try await Console.readPromptInput(from: input)
    }
}

@Test(arguments: ["\n", "yes\n", "no\r\n", "partial"])
func promptDistinguishesBlankLinesFromEOF(text: String) async throws {
    let input = AsyncStream<ByteBuffer> { continuation in
        for byte in text.utf8 { continuation.yield(ByteBuffer(bytes: [byte])) }
        continuation.finish()
    }
    let expected = text.trimmingCharacters(in: .newlines)
    #expect(try await Console.readPromptInput(from: input) == expected)
}

@Test func revocationDisplayAcceptsSparseCertificateMetadata() {
    let missing = DeveloperServicesCertificate(_type: .certificates, id: "synthetic-certificate")
    #expect(XToolInstallerDelegate.certificateDescription(missing) == "- synthetic-certificate (expires unknown)")
    let unnamed = DeveloperServicesCertificate(
        _type: .certificates, id: "synthetic", attributes: .init(displayName: "Synthetic display name")
    )
    #expect(XToolInstallerDelegate.certificateDescription(unnamed) == "- Synthetic display name (expires unknown)")
}
