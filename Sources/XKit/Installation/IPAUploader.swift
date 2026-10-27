//
//  IPAUploader.swift
//  XKit
//
//  Created by Kabir Oberai on 14/11/19.
//  Copyright © 2019 Kabir Oberai. All rights reserved.
//

import Foundation
import SwiftyMobileDevice

public final class IPAUploader: Sendable {

    public enum Error: Swift.Error {
        case unexpectedSymlink(at: URL)
        case invalidWriteCount(Int)
    }

    private static let packagePath = URL(fileURLWithPath: "/PublicStaging")
    private static let bufferSize = 1 << 20 // 1 MB

    static func stagingLocation() -> URL {
        packagePath.appendingPathComponent("XTool-App-\(UUID().uuidString).ipa")
    }

    /// AFC can acknowledge only part of a buffer. Retry the remaining suffix,
    /// and stop on a stalled or invalid write instead of corrupting the IPA.
    static func writeChunk(
        _ buffer: Data,
        write: (Data) throws -> Int,
        progress: (Int) -> Void
    ) throws {
        var offset = 0
        while offset < buffer.count {
            try Task.checkCancellation()
            let remaining = buffer.dropFirst(offset)
            let written = try write(remaining)
            guard written > 0 && written <= remaining.count else {
                throw Error.invalidWriteCount(written)
            }
            offset += written
            progress(written)
        }
    }

    public final class UploadedIPA: Sendable {
        public let uploader: IPAUploader
        let location: URL
        fileprivate init(uploader: IPAUploader, location: URL) {
            self.uploader = uploader
            self.location = location
        }

        deinit { delete() }

        public func delete() {
            try? uploader.client.removeItemAndContents(at: location)
        }
    }

    private let client: AFCClient
    public init(connection: Connection) async throws {
        self.client = try await connection.startClient()
    }

    private func upload(_ src: URL, to dest: URL, progress: (Double) -> Void) async throws {
        let srcData = try Data(contentsOf: src)
        let size = srcData.count
        let sizeDouble = Double(size)
        let destFile = try client.open(dest, mode: .writeOnly)

        let bufferSize = Self.bufferSize

        var totalWritten = 0
        while totalWritten != size {
            if totalWritten != 0 {
                await Task.yield()
                try Task.checkCancellation()
            }
            let buf = srcData.dropFirst(totalWritten).prefix(bufferSize)
            try Self.writeChunk(buf, write: destFile.write) { written in
                totalWritten += written
                progress(Double(totalWritten) / sizeDouble)
            }
        }
    }

    public func upload(app: URL, progress: (Double) -> Void) async throws -> UploadedIPA {
        if try !client.fileExists(at: Self.packagePath) {
            try client.createDirectory(at: Self.packagePath)
        }

        let dest = Self.stagingLocation()
        do {
            try await upload(app, to: dest, progress: progress)
        } catch {
            try? client.removeItemAndContents(at: dest)
            throw error
        }

        return UploadedIPA(uploader: self, location: dest)
    }

}
