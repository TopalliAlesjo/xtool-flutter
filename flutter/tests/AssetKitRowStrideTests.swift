import Foundation
import Testing
import CLZFSE
@testable import AssetKit

@Suite("Bitmap row stride regression")
struct AssetKitRowStrideTests {
    @Test("Decoded chunks match the declared stride, pixels and zero padding",
          arguments: [1, 20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180])
    func rows(width: Int) throws {
        for bytesPerPixel in [2, 4, 8] {
            for height in [1, 2, 3, 4, 29] {
                let packed = width * bytesPerPixel
                let stride = (packed + 15) & ~15
                // Row-specific data exposes shifts even when padding is zero.
                let pixels = (0..<packed * height).map { UInt8(truncatingIfNeeded: $0 + $0 / packed) }
                let encoded = [UInt8](MLECBody.encode(
                    width: UInt32(width), height: UInt32(height),
                    bytesPerPixel: UInt32(bytesPerPixel), opaque: false, pixels: pixels
                ))
                func uint32(_ offset: Int) -> Int {
                    (0..<4).reduce(0) { $0 | Int(encoded[offset + $1]) << (8 * $1) }
                }
                var offset = 16
                var decoded: [UInt8] = []
                var totalRows = 0
                for _ in 0..<uint32(12) {
                    let rows = uint32(offset + 12)
                    let count = uint32(offset + 16)
                    let payload = Array(encoded[offset + 20..<offset + 20 + count])
                    var output = [UInt8](repeating: 0xEE, count: stride * rows + 1)
                    let written = output.withUnsafeMutableBufferPointer { destination in
                        payload.withUnsafeBufferPointer { source in
                            lzfse_decode_buffer(destination.baseAddress!, destination.count,
                                                source.baseAddress!, source.count, nil)
                        }
                    }
                    #expect(written == stride * rows)
                    decoded.append(contentsOf: output.prefix(written))
                    totalRows += rows
                    offset += 20 + count
                }
                #expect(totalRows == height)
                #expect(offset == encoded.count)
                #expect(decoded.count == stride * height)
                guard decoded.count == stride * height else { continue }
                for row in 0..<height {
                    #expect(Array(decoded[row * stride..<row * stride + packed]) ==
                            Array(pixels[row * packed..<(row + 1) * packed]))
                    #expect(decoded[row * stride + packed..<(row + 1) * stride].allSatisfy { $0 == 0 })
                }
            }
        }
    }
}
