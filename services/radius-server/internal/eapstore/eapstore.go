package eapstore

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

// EAPSession tracks in-flight EAP conversations
type EAPSession struct {
	SessionID string      `json:"session_id"`
	State     []byte      `json:"state,omitempty"`
	TenantID  string      `json:"tenant_id"`
	NASIP     string      `json:"nas_ip"`
	MAC       string      `json:"mac"`
	Username  string      `json:"username"`
	EAPType   string      `json:"eap_type"`
	TLSState  int         `json:"tls_state"`
	CreatedAt time.Time   `json:"created_at"`
}

// Store is the interface for EAP session storage
type Store interface {
	Get(ctx context.Context, key string) (*EAPSession, bool)
	Set(ctx context.Context, key string, session *EAPSession)
	Delete(ctx context.Context, key string)
	Count(ctx context.Context) int
	Close()
}

const (
	eapSessionTTL = 60 * time.Second
	eapKeyPrefix  = "eap_session:"
)

// NewStore creates an EAP session store based on configuration.
// If EAP_SESSION_STORE=redis and a valid Redis connection is available,
// it returns a RedisStore. Otherwise, it falls back to an in-memory store.
func NewStore(logger *zap.Logger) Store {
	storeType := os.Getenv("EAP_SESSION_STORE")
	if storeType == "redis" {
		redisAddr := os.Getenv("REDIS_HOST")
		if redisAddr == "" {
			redisAddr = "localhost"
		}
		redisPort := os.Getenv("REDIS_PORT")
		if redisPort == "" {
			redisPort = "6379"
		}
		redisPass := os.Getenv("REDIS_PASSWORD")

		client := redis.NewClient(&redis.Options{
			Addr:     fmt.Sprintf("%s:%s", redisAddr, redisPort),
			Password: redisPass,
			DB:       1, // Use DB 1 for EAP sessions to avoid collision
		})

		ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		if err := client.Ping(ctx).Err(); err != nil {
			logger.Warn("Redis unavailable for EAP sessions, falling back to in-memory",
				zap.Error(err))
			return NewMemoryStore(logger)
		}
		logger.Info("EAP session store using Redis",
			zap.String("addr", fmt.Sprintf("%s:%s", redisAddr, redisPort)))
		return &RedisStore{client: client, logger: logger}
	}
	return NewMemoryStore(logger)
}

// RedisStore stores EAP sessions in Redis for cross-replica sharing
type RedisStore struct {
	client *redis.Client
	logger *zap.Logger
}

func (r *RedisStore) Get(ctx context.Context, key string) (*EAPSession, bool) {
	data, err := r.client.Get(ctx, eapKeyPrefix+key).Bytes()
	if err != nil {
		return nil, false
	}
	var session EAPSession
	if err := json.Unmarshal(data, &session); err != nil {
		r.logger.Warn("Failed to unmarshal EAP session", zap.Error(err))
		return nil, false
	}
	return &session, true
}

func (r *RedisStore) Set(ctx context.Context, key string, session *EAPSession) {
	data, err := json.Marshal(session)
	if err != nil {
		r.logger.Warn("Failed to marshal EAP session", zap.Error(err))
		return
	}
	r.client.Set(ctx, eapKeyPrefix+key, data, eapSessionTTL)
}

func (r *RedisStore) Delete(ctx context.Context, key string) {
	r.client.Del(ctx, eapKeyPrefix+key)
}

func (r *RedisStore) Count(ctx context.Context) int {
	keys, err := r.client.Keys(ctx, eapKeyPrefix+"*").Result()
	if err != nil {
		return 0
	}
	return len(keys)
}

func (r *RedisStore) Close() {
	if r.client != nil {
		r.client.Close()
	}
}

// MemoryStore stores EAP sessions in-memory (single-replica only)
type MemoryStore struct {
	mu       sync.RWMutex
	sessions map[string]*EAPSession
	logger   *zap.Logger
	stop     chan struct{}
}

// NewMemoryStore creates a new in-memory EAP session store
func NewMemoryStore(logger *zap.Logger) *MemoryStore {
	m := &MemoryStore{
		sessions: make(map[string]*EAPSession),
		logger:   logger,
		stop:     make(chan struct{}),
	}
	go m.cleanup()
	return m
}

func (m *MemoryStore) Get(_ context.Context, key string) (*EAPSession, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	s, ok := m.sessions[key]
	return s, ok
}

func (m *MemoryStore) Set(_ context.Context, key string, session *EAPSession) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.sessions[key] = session
}

func (m *MemoryStore) Delete(_ context.Context, key string) {
	m.mu.Lock()
	defer m.mu.Unlock()
	delete(m.sessions, key)
}

func (m *MemoryStore) Count(_ context.Context) int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.sessions)
}

func (m *MemoryStore) Close() {
	close(m.stop)
}

func (m *MemoryStore) cleanup() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-m.stop:
			return
		case <-ticker.C:
			now := time.Now()
			m.mu.Lock()
			expired := 0
			for key, sess := range m.sessions {
				if now.Sub(sess.CreatedAt) > eapSessionTTL {
					delete(m.sessions, key)
					expired++
				}
			}
			m.mu.Unlock()
			if expired > 0 {
				m.logger.Info("EAP session cleanup",
					zap.Int("expired", expired),
					zap.Int("remaining", m.Count(context.Background())))
			}
		}
	}
}
