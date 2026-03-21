package circuitbreaker

import (
	"errors"
	"sync"
	"time"
)

// State represents the circuit breaker state
type State int

const (
	StateClosed   State = iota // Normal operation, requests pass through
	StateOpen                  // Failures exceeded threshold, requests blocked
	StateHalfOpen              // Testing if service recovered
)

var (
	ErrCircuitOpen = errors.New("circuit breaker is open")
)

// CircuitBreaker implements the circuit breaker pattern for gRPC calls
type CircuitBreaker struct {
	mu sync.RWMutex

	state           State
	failureCount    int
	successCount    int
	lastFailure     time.Time
	lastStateChange time.Time

	// Configuration
	maxFailures     int
	resetTimeout    time.Duration
	halfOpenMaxReqs int
}

// Options configures the circuit breaker
type Options struct {
	MaxFailures     int
	ResetTimeout    time.Duration
	HalfOpenMaxReqs int
}

// DefaultOptions returns sensible defaults for RADIUS use
func DefaultOptions() Options {
	return Options{
		MaxFailures:     5,
		ResetTimeout:    30 * time.Second,
		HalfOpenMaxReqs: 3,
	}
}

// New creates a new circuit breaker
func New(opts Options) *CircuitBreaker {
	if opts.MaxFailures <= 0 {
		opts.MaxFailures = 5
	}
	if opts.ResetTimeout <= 0 {
		opts.ResetTimeout = 30 * time.Second
	}
	if opts.HalfOpenMaxReqs <= 0 {
		opts.HalfOpenMaxReqs = 3
	}

	return &CircuitBreaker{
		state:           StateClosed,
		maxFailures:     opts.MaxFailures,
		resetTimeout:    opts.ResetTimeout,
		halfOpenMaxReqs: opts.HalfOpenMaxReqs,
		lastStateChange: time.Now(),
	}
}

// Allow checks if a request should be allowed through
func (cb *CircuitBreaker) Allow() error {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	switch cb.state {
	case StateClosed:
		return nil
	case StateOpen:
		if time.Since(cb.lastFailure) > cb.resetTimeout {
			// Transition to half-open will happen on next call
			return nil
		}
		return ErrCircuitOpen
	case StateHalfOpen:
		if cb.successCount < cb.halfOpenMaxReqs {
			return nil
		}
		return ErrCircuitOpen
	}
	return nil
}

// RecordSuccess records a successful call
func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	switch cb.state {
	case StateHalfOpen:
		cb.successCount++
		if cb.successCount >= cb.halfOpenMaxReqs {
			cb.state = StateClosed
			cb.failureCount = 0
			cb.successCount = 0
			cb.lastStateChange = time.Now()
		}
	case StateClosed:
		cb.failureCount = 0
	case StateOpen:
		if time.Since(cb.lastFailure) > cb.resetTimeout {
			cb.successCount = 1
			cb.failureCount = 0
			cb.lastStateChange = time.Now()
			if cb.successCount >= cb.halfOpenMaxReqs {
				cb.state = StateClosed
				cb.successCount = 0
			} else {
				cb.state = StateHalfOpen
			}
		}
	}
}

// RecordFailure records a failed call
func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()

	cb.lastFailure = time.Now()
	cb.failureCount++

	switch cb.state {
	case StateClosed:
		if cb.failureCount >= cb.maxFailures {
			cb.state = StateOpen
			cb.lastStateChange = time.Now()
		}
	case StateHalfOpen:
		cb.state = StateOpen
		cb.successCount = 0
		cb.lastStateChange = time.Now()
	}
}

// GetState returns the current state
func (cb *CircuitBreaker) GetState() State {
	cb.mu.RLock()
	defer cb.mu.RUnlock()
	return cb.state
}

// Stats returns circuit breaker statistics
func (cb *CircuitBreaker) Stats() map[string]interface{} {
	cb.mu.RLock()
	defer cb.mu.RUnlock()

	stateStr := "closed"
	switch cb.state {
	case StateOpen:
		stateStr = "open"
	case StateHalfOpen:
		stateStr = "half_open"
	}

	return map[string]interface{}{
		"state":             stateStr,
		"failure_count":     cb.failureCount,
		"success_count":     cb.successCount,
		"last_failure":      cb.lastFailure,
		"last_state_change": cb.lastStateChange,
	}
}
