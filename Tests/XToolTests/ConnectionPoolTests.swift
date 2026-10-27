import Testing
@testable import XKit

private final class PoolValue: Sendable {}
private enum PoolFailure: Error { case unavailable }
private actor Attempts {
    private(set) var count = 0
    func next() -> Int {
        count += 1
        return count
    }
}

@Test func failedConnectionCreationCanBeRetried() async throws {
    let pool = WeakPool<String, PoolValue, PoolFailure>()
    let attempts = Attempts()
    do {
        _ = try await pool.value(key: "synthetic-device") { () async throws(PoolFailure) -> PoolValue in
            _ = await attempts.next()
            throw .unavailable
        }
        Issue.record("The first connection must fail")
    } catch PoolFailure.unavailable {
        // Expected: the failed task must be evicted before the next attempt.
    }
    let value = try await pool.value(key: "synthetic-device") { () async throws(PoolFailure) -> PoolValue in
        _ = await attempts.next()
        return PoolValue()
    }
    #expect(await attempts.count == 2)
    let cached = try await pool.value(key: "synthetic-device") { () async throws(PoolFailure) -> PoolValue in
        throw .unavailable
    }
    #expect(cached === value)
}

@Test func concurrentConnectionsShareTheSameCreation() async throws {
    let pool = WeakPool<String, PoolValue, PoolFailure>()
    let attempts = Attempts()
    let create: @Sendable () async throws(PoolFailure) -> PoolValue = {
        _ = await attempts.next()
        for _ in 0..<10 { await Task.yield() }
        return PoolValue()
    }
    async let first = pool.value(key: "synthetic-device", create: create)
    async let second = pool.value(key: "synthetic-device", create: create)
    let values = try await (first, second)
    #expect(values.0 === values.1)
    #expect(await attempts.count == 1)
}
