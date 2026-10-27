//
//  KeyValueStorage.swift
//  XKit
//
//  Created by Kabir Oberai on 08/04/20.
//  Copyright © 2020 Kabir Oberai. All rights reserved.
//

import Foundation
import ConcurrencyExtras
import Dependencies

public enum KeyValueStorageError: Error {
    case stringConversionFailure
}

public protocol KeyValueStorage: Sendable {
    func data(forKey key: String) throws -> Data?
    func setData(_ data: Data?, forKey key: String) throws
    // default implementations provided
    func string(forKey key: String) throws -> String?
    func setString(_ string: String?, forKey key: String) throws
}

private enum KeyValueStorageDependencyKey: DependencyKey {
    static let testValue: KeyValueStorage = UnimplementedKeyValueStorage()
    static let liveValue: KeyValueStorage = DirectoryStorage()
}

extension DependencyValues {
    public var keyValueStorage: KeyValueStorage {
        get { self[KeyValueStorageDependencyKey.self] }
        set { self[KeyValueStorageDependencyKey.self] = newValue }
    }
}

extension KeyValueStorage {
    public func string(forKey key: String) throws -> String? {
        try data(forKey: key).map {
            try String(data: $0, encoding: .utf8).orThrow(KeyValueStorageError.stringConversionFailure)
        }
    }

    public func setString(_ string: String?, forKey key: String) throws {
        let data = try string.map { try $0.data(using: .utf8).orThrow(KeyValueStorageError.stringConversionFailure) }
        try setData(data, forKey: key)
    }

    public subscript(dataForKey key: String) -> Data? {
        get { try? data(forKey: key) }
        nonmutating set { try? setData(newValue, forKey: key) }
    }

    public subscript(stringForKey key: String) -> String? {
        get { try? string(forKey: key) }
        nonmutating set { try? setString(newValue, forKey: key) }
    }
}

public struct UnimplementedKeyValueStorage: KeyValueStorage {
    public func data(forKey key: String) throws -> Data? {
        unimplemented(placeholder: nil)
    }

    public func setData(_ data: Data?, forKey key: String) throws {
        unimplemented()
    }
}

public struct MemoryKeyValueStorage: KeyValueStorage {

    private let dict = LockIsolated<[String: Data]>([:])
    public init() {}

    public func data(forKey key: String) throws -> Data? {
        dict[key]
    }

    public func setData(_ data: Data?, forKey key: String) throws {
        dict.withValue { $0[key] = data }
    }

}

public struct DirectoryStorage: KeyValueStorage {
    @Dependency(\.persistentDirectory) var directory

    private var base: URL { directory.appendingPathComponent("data") }

    public init() {}

    private func url(for key: String) -> URL {
        base.appendingPathComponent(key)
    }

    public func data(forKey key: String) throws -> Data? {
        guard FileManager.default.fileExists(atPath: base.path) else { return nil }
        try makeDirectoryPrivate()
        let file = url(for: key)
        guard FileManager.default.fileExists(atPath: file.path) else { return nil }
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: file.path)
        return try Data(contentsOf: file)
    }

    private func makeDirectoryPrivate() throws {
        try FileManager.default.createDirectory(
            at: base,
            withIntermediateDirectories: true,
            attributes: [.posixPermissions: 0o700]
        )
        // Also migrate directories created by older releases before accessing secrets.
        try FileManager.default.setAttributes([.posixPermissions: 0o700], ofItemAtPath: base.path)
    }

    public func setData(_ data: Data?, forKey key: String) throws {
        let url = url(for: key)
        if let data = data {
            try makeDirectoryPrivate()
            // The private directory protects the temporary file throughout atomic replacement.
            try data.write(to: url, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
        } else {
            guard FileManager.default.fileExists(atPath: base.path) else { return }
            try makeDirectoryPrivate()
            do {
                try FileManager.default.removeItem(at: url)
            } catch CocoaError.fileNoSuchFile {
                // Deleting an absent key is idempotent, like the other storage adapters.
            }
        }
    }
}

#if canImport(Security)
import Security

public struct KeychainStorage: KeyValueStorage {

    public let service: String?
    public init(service: String? = nil) {
        self.service = service
    }

    private let lock = NSLock()

    private static func check(_ result: OSStatus, ignoreNotFound: Bool = false) throws {
        if result != errSecSuccess {
            if ignoreNotFound && result == errSecItemNotFound { return }
            let info: [String: Any]?
            if let message = SecCopyErrorMessageString(result, nil) {
                info = [NSLocalizedDescriptionKey: message as String]
            } else {
                info = nil
            }
            throw NSError(domain: NSOSStatusErrorDomain, code: .init(result), userInfo: info)
        }
    }

    private func makeQuery(forKey key: String, _ parameters: [CFString: Any]) -> CFDictionary {
        var query: [CFString: Any] = [
            kSecClass: kSecClassGenericPassword,
            kSecAttrAccount: key,
            kSecUseDataProtectionKeychain: true,
        ]
        query[kSecAttrService] = service
        query.merge(parameters) { _, b in b }
        return query as CFDictionary
    }

    public func data(forKey key: String) throws -> Data? {
        lock.lock()
        defer { lock.unlock() }

        let query = makeQuery(forKey: key, [
            kSecReturnData: true
        ])

        var result: AnyObject?
        try Self.check(SecItemCopyMatching(query, &result), ignoreNotFound: true)

        return result as? Data
    }

    public func setData(_ data: Data?, forKey key: String) throws {
        lock.lock()
        defer { lock.unlock() }

        // remove old before setting new value
        try Self.check(SecItemDelete(makeQuery(forKey: key, [:])), ignoreNotFound: true)

        guard let data = data else { return }

        let query = makeQuery(forKey: key, [
            kSecValueData: data,
            kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlock
        ])

        try Self.check(SecItemAdd(query, nil))
    }

}
#endif
