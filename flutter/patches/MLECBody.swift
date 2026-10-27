// AssetKit 705ce2f2, MIT (LICENSE retained in the prepared package).
// Local fix: pad bitmap rows to the stride declared by TVLEntry.bytesPerRow.
import Foundation

/// MLEC wrapper for bitmap pixels, framed in KCBC chunks.
enum MLECBody {
    static func encode(
        width: UInt32,
        height: UInt32,
        bytesPerPixel: UInt32 = 4,
        opaque: Bool,
        pixels: [UInt8]
    ) -> Data {
        let packedBytesPerRow = Int(width) * Int(bytesPerPixel)
        let bytesPerRow = (packedBytesPerRow + 15) & ~15
        precondition(pixels.count == packedBytesPerRow * Int(height))
        // CoreUI advances each row using TVL 1007's 16-byte-aligned stride.
        // Compressing tightly packed rows shears 29/58/87/167px app icons.
        let padded: [UInt8]
        if bytesPerRow == packedBytesPerRow {
            padded = pixels
        } else {
            var buffer = [UInt8](repeating: 0, count: bytesPerRow * Int(height))
            for row in 0..<Int(height) {
                let source = row * packedBytesPerRow
                let destination = row * bytesPerRow
                buffer.replaceSubrange(
                    destination..<destination + packedBytesPerRow,
                    with: pixels[source..<source + packedBytesPerRow]
                )
            }
            padded = buffer
        }
        let rowsPerChunk = height / 3
        let remainder = height % 3
        var chunks: [(rows: UInt32, payload: [UInt8])] = []
        if rowsPerChunk == 0 {
            chunks.append((rows: height, payload: LZFSE.encode(padded)))
        } else {
            for index in 0..<3 {
                let start = Int(index) * Int(rowsPerChunk) * bytesPerRow
                let end = start + Int(rowsPerChunk) * bytesPerRow
                chunks.append((rows: rowsPerChunk, payload: LZFSE.encode(Array(padded[start..<end]))))
            }
            if remainder > 0 {
                let start = 3 * Int(rowsPerChunk) * bytesPerRow
                chunks.append((rows: remainder, payload: LZFSE.encode(Array(padded[start...]))))
            }
        }

        var writer = ByteWriter()
        writer.writeFourCC("MLEC")
        writer.writeLE(UInt32(opaque ? 3 : 1))
        writer.writeLE(UInt32(4)) // CoreUI's constant, including gray formats.
        writer.writeLE(UInt32(chunks.count))
        for chunk in chunks {
            writer.writeFourCC("KCBC")
            writer.writeZeros(8)
            writer.writeLE(chunk.rows)
            writer.writeLE(UInt32(chunk.payload.count))
            writer.write(chunk.payload)
        }
        return writer.data
    }
}
