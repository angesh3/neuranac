package circuitbreaker

import (
	"testing"
	"time"
)

func TestNewCircuitBreaker(t *testing.T) {
	cb := New(DefaultOptions())
	if cb.GetState() != StateClosed {
		t.Error("new circuit breaker should be closed")
	}
	if err := cb.Allow(); err != nil {
		t.Errorf("closed circuit breaker should allow requests: %v", err)
	}
}

func TestClosedToOpen(t *testing.T) {
	cb := New(Options{MaxFailures: 3, ResetTimeout: 1 * time.Second, HalfOpenMaxReqs: 1})

	// 3 failures should trip the breaker
	for i := 0; i < 3; i++ {
		cb.RecordFailure()
	}
	if cb.GetState() != StateOpen {
		t.Errorf("expected open after %d failures, got %d", 3, cb.GetState())
	}
	if err := cb.Allow(); err != ErrCircuitOpen {
		t.Error("open circuit breaker should reject requests")
	}
}

func TestOpenToHalfOpen(t *testing.T) {
	cb := New(Options{MaxFailures: 2, ResetTimeout: 50 * time.Millisecond, HalfOpenMaxReqs: 1})

	cb.RecordFailure()
	cb.RecordFailure()
	if cb.GetState() != StateOpen {
		t.Fatal("expected open state")
	}

	// Wait for reset timeout
	time.Sleep(60 * time.Millisecond)

	// Should allow because reset timeout passed
	if err := cb.Allow(); err != nil {
		t.Errorf("should allow after reset timeout: %v", err)
	}

	// Recording success should transition to half-open then closed
	cb.RecordSuccess()
	if cb.GetState() != StateClosed {
		t.Errorf("expected closed after success in half-open, got %d", cb.GetState())
	}
}

func TestHalfOpenFailure(t *testing.T) {
	cb := New(Options{MaxFailures: 1, ResetTimeout: 50 * time.Millisecond, HalfOpenMaxReqs: 2})

	cb.RecordFailure() // trips to open
	time.Sleep(60 * time.Millisecond)
	cb.RecordSuccess() // transitions to half-open

	cb.RecordFailure() // should go back to open
	if cb.GetState() != StateOpen {
		t.Errorf("expected open after failure in half-open, got %d", cb.GetState())
	}
}

func TestSuccessResetsClosed(t *testing.T) {
	cb := New(Options{MaxFailures: 3, ResetTimeout: 1 * time.Second, HalfOpenMaxReqs: 1})

	cb.RecordFailure()
	cb.RecordFailure()
	cb.RecordSuccess() // should reset failure count

	// After reset, one more failure shouldn't trip
	cb.RecordFailure()
	if cb.GetState() != StateClosed {
		t.Error("should still be closed after success reset")
	}
}

func TestStats(t *testing.T) {
	cb := New(DefaultOptions())
	cb.RecordFailure()
	stats := cb.Stats()

	if stats["state"] != "closed" {
		t.Errorf("expected closed, got %v", stats["state"])
	}
	if stats["failure_count"].(int) != 1 {
		t.Errorf("expected 1 failure, got %v", stats["failure_count"])
	}
}

func TestDefaultOptions(t *testing.T) {
	opts := DefaultOptions()
	if opts.MaxFailures != 5 {
		t.Errorf("expected 5, got %d", opts.MaxFailures)
	}
	if opts.ResetTimeout != 30*time.Second {
		t.Errorf("expected 30s, got %v", opts.ResetTimeout)
	}
	if opts.HalfOpenMaxReqs != 3 {
		t.Errorf("expected 3, got %d", opts.HalfOpenMaxReqs)
	}
}

func TestZeroOptions(t *testing.T) {
	cb := New(Options{})
	// Should use defaults
	if err := cb.Allow(); err != nil {
		t.Error("should allow with zero options")
	}
}
