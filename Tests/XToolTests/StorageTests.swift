import Foundation
import Testing
import Dependencies
@testable import XKit

private func withSyntheticStorage(_ body: (DirectoryStorage, URL) throws -> Void) throws {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    defer { try? FileManager.default.removeItem(at: directory) }
    try withDependencies {
        $0.persistentDirectory = directory
    } operation: {
        try body(DirectoryStorage(), directory.appendingPathComponent("data"))
    }
}

@Test func storedSecretsHavePrivatePermissionsAndSurviveReplacement() throws {
    try withSyntheticStorage { storage, directory in
        try storage.setData(Data("synthetic-token".utf8), forKey: "test-token")
        try storage.setData(Data("replacement".utf8), forKey: "test-token")
        let attributes = try FileManager.default.attributesOfItem(atPath: directory.path)
        let fileAttributes = try FileManager.default.attributesOfItem(atPath: directory.appendingPathComponent("test-token").path)
        #expect((attributes[.posixPermissions] as? NSNumber)?.intValue == 0o700)
        #expect((fileAttributes[.posixPermissions] as? NSNumber)?.intValue == 0o600)
        #expect(try storage.data(forKey: "test-token") == Data("replacement".utf8))
    }
}

@Test func readingLegacySecretsRestrictsExistingPermissions() throws {
    try withSyntheticStorage { storage, directory in
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let file = directory.appendingPathComponent("legacy")
        try Data("synthetic-legacy".utf8).write(to: file)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: directory.path)
        try FileManager.default.setAttributes([.posixPermissions: 0o644], ofItemAtPath: file.path)
        #expect(try storage.data(forKey: "legacy") == Data("synthetic-legacy".utf8))
        let directoryAttributes = try FileManager.default.attributesOfItem(atPath: directory.path)
        let fileAttributes = try FileManager.default.attributesOfItem(atPath: file.path)
        #expect((directoryAttributes[.posixPermissions] as? NSNumber)?.intValue == 0o700)
        #expect((fileAttributes[.posixPermissions] as? NSNumber)?.intValue == 0o600)
    }
}

@Test func deletingStorageKeysIsIdempotent() throws {
    try withSyntheticStorage { storage, _ in
        try storage.setData(nil, forKey: "missing")
        try storage.setData(Data([1]), forKey: "existing")
        try storage.setData(nil, forKey: "existing")
        try storage.setData(nil, forKey: "existing")
        #expect(try storage.data(forKey: "existing") == nil)
    }
}

@Test func nilSigningInfoDeletesItsStorageKey() throws {
    let storage = MemoryKeyValueStorage()
    try storage.setData(Data("old synthetic key".utf8), forKey: "test-identity")
    try withDependencies {
        $0.keyValueStorage = storage
    } operation: {
        try KeyValueSigningInfoManager().setInfo(nil, forIdentityID: "test-identity")
        #expect(try storage.data(forKey: "test-identity") == nil)
    }
}
