import Foundation
import Testing
import CLZFSE
@testable import AssetKit

/// Optional end-to-end gate against the actual catalog, not a test-only encoder.
@Suite("Compiled icon pixels")
struct CompiledIconTests {
    @Test("Every compiled AppIcon has the original pixels at its declared stride",
          .enabled(if: ProcessInfo.processInfo.environment["IOS_ICON_BUNDLE"] != nil))
    func originalPixels() throws {
        let environment = ProcessInfo.processInfo.environment
        let bundle = URL(fileURLWithPath: try #require(environment["IOS_ICON_BUNDLE"]))
        let source = URL(fileURLWithPath: try #require(environment["IOS_ICON_SOURCE"]))
        let catalog = source.appendingPathComponent("ios/Runner/Assets.xcassets/AppIcon.appiconset")
        let contents = try Data(contentsOf: catalog.appendingPathComponent("Contents.json"))
        let json = try #require(JSONSerialization.jsonObject(with: contents) as? [String: Any])
        let images = try #require(json["images"] as? [[String: Any]])
        let filenames = Set(images.compactMap { $0["filename"] as? String })
        let car = try Data(contentsOf: bundle.appendingPathComponent("Assets.car"))
        var scan = car.startIndex
        var found: Set<String> = []
        func uint32(_ offset: Int) -> Int {
            (0..<4).reduce(0) { $0 | Int(car[offset + $1]) << (8 * $1) }
        }
        while let range = car.range(of: Data("ISTC".utf8), in: scan..<car.endIndex) {
            scan = range.upperBound
            let start = range.lowerBound
            guard start + 184 <= car.count else { continue }
            let nameBytes = car[start + 40..<start + 168].prefix { $0 != 0 }
            guard let name = String(bytes: nameBytes, encoding: .utf8), filenames.contains(name),
                  car[start + 24..<start + 28] == Data("BGRA".utf8) else { continue }
            let original = try PNGSource.decodeBGRA(Data(contentsOf: catalog.appendingPathComponent(name)))
            let width = uint32(start + 12)
            let height = uint32(start + 16)
            #expect(width == Int(original.width) && height == Int(original.height))
            let tvlEnd = start + 184 + uint32(start + 168)
            var tvl = start + 184
            var stride = 0
            while tvl < tvlEnd {
                if uint32(tvl) == 1007 { stride = uint32(tvl + 8) }
                tvl += 8 + uint32(tvl + 4)
            }
            #expect(stride >= width * 4)
            var chunk = tvlEnd + 16
            var decoded: [UInt8] = []
            for _ in 0..<uint32(tvlEnd + 12) {
                let rows = uint32(chunk + 12)
                let size = uint32(chunk + 16)
                let payload = Array(car[chunk + 20..<chunk + 20 + size])
                var output = [UInt8](repeating: 0xEE, count: stride * rows + 1)
                let written = output.withUnsafeMutableBufferPointer { destination in
                    payload.withUnsafeBufferPointer { input in
                        lzfse_decode_buffer(destination.baseAddress!, destination.count,
                                            input.baseAddress!, input.count, nil)
                    }
                }
                #expect(written == stride * rows, "\(name): decoded rows must match TVL stride")
                decoded.append(contentsOf: output.prefix(written))
                chunk += 20 + size
            }
            #expect(decoded.count == stride * height, "\(name): bitmap length")
            if decoded.count == stride * height {
                for row in 0..<height {
                    #expect(Array(decoded[row * stride..<row * stride + width * 4]) ==
                            Array(original.bgra8[row * width * 4..<(row + 1) * width * 4]),
                            "\(name): row \(row) must preserve original pixels")
                }
            }
            found.insert(name)
        }
        #expect(found == filenames, "All original icon formats must be checked")
    }
}
