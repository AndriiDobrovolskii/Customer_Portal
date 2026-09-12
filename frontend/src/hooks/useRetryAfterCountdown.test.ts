// Unit test for useRetryAfterCountdown (FR-12, OD-1). A small, non-network
// local-state hook: ticks `secondsRemaining` down to zero from a supplied
// `retryAfterSeconds`, exposing `isBlocked` while > 0. Shared by
// NewTicketScreen.tsx and TicketDetailScreen.tsx's reply composer so both
// 429 call sites get identical behavior without duplicating it.
//
// Fake timers are confined to this file (never mixed with userEvent/waitFor
// at the screen level, per docs/tests/US-5.3-test-strategy.md) — advanced
// synchronously inside `act()`.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "@testing-library/react";
import { renderHookWithProviders } from "../test/test-utils";
import { useRetryAfterCountdown } from "./useRetryAfterCountdown";

describe("useRetryAfterCountdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("test_use_retry_after_countdown_undefined_input_yields_zero_seconds_remaining_and_not_blocked", () => {
    // Arrange / Act
    const { result } = renderHookWithProviders(() => useRetryAfterCountdown(undefined));

    // Assert
    expect(result.current.secondsRemaining).toBe(0);
    expect(result.current.isBlocked).toBe(false);
  });

  it("test_use_retry_after_countdown_starts_blocked_with_the_supplied_seconds_remaining", () => {
    // Arrange / Act
    const { result } = renderHookWithProviders(() => useRetryAfterCountdown(30));

    // Assert
    expect(result.current.secondsRemaining).toBe(30);
    expect(result.current.isBlocked).toBe(true);
  });

  it("test_use_retry_after_countdown_ticks_down_to_zero_and_isblocked_flips_false", () => {
    // Arrange
    const { result } = renderHookWithProviders(() => useRetryAfterCountdown(2));
    expect(result.current.isBlocked).toBe(true);

    // Act
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    // Assert (mid-countdown)
    expect(result.current.secondsRemaining).toBe(1);
    expect(result.current.isBlocked).toBe(true);

    // Act
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    // Assert (elapsed)
    expect(result.current.secondsRemaining).toBe(0);
    expect(result.current.isBlocked).toBe(false);
  });

  it("test_use_retry_after_countdown_clears_its_interval_on_unmount", () => {
    // Arrange
    const clearIntervalSpy = vi.spyOn(globalThis, "clearInterval");
    const { unmount } = renderHookWithProviders(() => useRetryAfterCountdown(5));

    // Act
    unmount();

    // Assert
    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });

  it("test_use_retry_after_countdown_reinitializes_when_a_new_retry_after_seconds_value_arrives", () => {
    // Arrange: a second, distinct 429 (e.g. a resubmission attempt while
    // still blocked) supplies a new retryAfterSeconds value.
    let seconds: number | undefined = 10;
    const { result, rerender } = renderHookWithProviders(() => useRetryAfterCountdown(seconds));
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.secondsRemaining).toBe(5);

    // Act
    seconds = 20;
    rerender();

    // Assert
    expect(result.current.secondsRemaining).toBe(20);
    expect(result.current.isBlocked).toBe(true);
  });
});
