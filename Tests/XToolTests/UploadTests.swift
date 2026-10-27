import Foundation
import Testing
@testable import XKit

@Test func partialUploadsOnlyRetryTheUnwrittenSuffix() throws {
    let original = Data([1, 2, 3, 4, 5, 6, 7])
    var uploaded = Data()
    var progress: [Int] = []
    try IPAUploader.writeChunk(original) { remaining in
        let count = min(3, remaining.count)
        uploaded.append(remaining.prefix(count))
        return count
    } progress: {
        progress.append($0)
    }
    #expect(uploaded == original)
    #expect(progress == [3, 3, 1])
}

@Test(arguments: [0, -1, 4])
func invalidUploadWriteCountsFailInsteadOfHanging(count: Int) {
    #expect(throws: IPAUploader.Error.self) {
        try IPAUploader.writeChunk(Data([1, 2, 3]), write: { _ in count }, progress: { _ in })
    }
}

@Test func eachUploadHasItsOwnStagingPath() {
    let first = IPAUploader.stagingLocation()
    let second = IPAUploader.stagingLocation()
    #expect(first != second)
    #expect(first.deletingLastPathComponent().path == "/PublicStaging")
    #expect(first.pathExtension == "ipa")
}
