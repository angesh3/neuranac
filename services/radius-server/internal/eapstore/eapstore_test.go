package eapstore

import (
	"context"
	"testing"
	"time"

	"go.uber.org/zap"
)

func testLogger() *zap.Logger {
	l, _ := zap.NewDevelopment()
	return l
}

func TestMemoryStoreSetGet(t *testing.T) {
	store := NewMemoryStore(testLogger())
	defer store.Close()
	ctx := context.Background()

	session := &EAPSession{
		SessionID: "test-1",
		TenantID:  "tenant-a",
		MAC:       "aa:bb:cc:dd:ee:ff",
		EAPType:   "eap-tls",
		TLSState:  0,
		CreatedAt: time.Now(),
	}

	store.Set(ctx, "key1", session)

	got, ok := store.Get(ctx, "key1")
	if !ok {
		t.Fatal("expected to find session")
	}
	if got.SessionID != "test-1" {
		t.Errorf("expected session ID test-1, got %s", got.SessionID)
	}
	if got.MAC != "aa:bb:cc:dd:ee:ff" {
		t.Errorf("expected MAC aa:bb:cc:dd:ee:ff, got %s", got.MAC)
	}
}

func TestMemoryStoreDelete(t *testing.T) {
	store := NewMemoryStore(testLogger())
	defer store.Close()
	ctx := context.Background()

	session := &EAPSession{
		SessionID: "test-2",
		CreatedAt: time.Now(),
	}

	store.Set(ctx, "key2", session)
	store.Delete(ctx, "key2")

	_, ok := store.Get(ctx, "key2")
	if ok {
		t.Error("expected session to be deleted")
	}
}

func TestMemoryStoreCount(t *testing.T) {
	store := NewMemoryStore(testLogger())
	defer store.Close()
	ctx := context.Background()

	for i := 0; i < 5; i++ {
		store.Set(ctx, string(rune('a'+i)), &EAPSession{
			SessionID: "s",
			CreatedAt: time.Now(),
		})
	}
	if store.Count(ctx) != 5 {
		t.Errorf("expected count 5, got %d", store.Count(ctx))
	}
}

func TestMemoryStoreGetMissing(t *testing.T) {
	store := NewMemoryStore(testLogger())
	defer store.Close()
	ctx := context.Background()

	_, ok := store.Get(ctx, "nonexistent")
	if ok {
		t.Error("expected not found for missing key")
	}
}

func TestMemoryStoreOverwrite(t *testing.T) {
	store := NewMemoryStore(testLogger())
	defer store.Close()
	ctx := context.Background()

	store.Set(ctx, "key", &EAPSession{SessionID: "v1", CreatedAt: time.Now()})
	store.Set(ctx, "key", &EAPSession{SessionID: "v2", CreatedAt: time.Now()})

	got, ok := store.Get(ctx, "key")
	if !ok {
		t.Fatal("expected to find session")
	}
	if got.SessionID != "v2" {
		t.Errorf("expected v2, got %s", got.SessionID)
	}
}

func TestNewStoreDefaultsToMemory(t *testing.T) {
	// Without EAP_SESSION_STORE env var, should default to memory
	store := NewStore(testLogger())
	defer store.Close()

	ctx := context.Background()
	store.Set(ctx, "test", &EAPSession{SessionID: "mem", CreatedAt: time.Now()})
	got, ok := store.Get(ctx, "test")
	if !ok {
		t.Fatal("expected to find session in default store")
	}
	if got.SessionID != "mem" {
		t.Errorf("expected mem, got %s", got.SessionID)
	}
}

func TestEAPSessionSerialization(t *testing.T) {
	session := &EAPSession{
		SessionID: "ser-1",
		TenantID:  "t1",
		NASIP:     "10.0.0.1",
		MAC:       "aa:bb:cc:dd:ee:ff",
		Username:  "user1",
		EAPType:   "peap",
		TLSState:  2,
		CreatedAt: time.Now(),
		State:     []byte{0x01, 0x02},
	}

	if session.SessionID != "ser-1" {
		t.Error("field assignment failed")
	}
	if session.TLSState != 2 {
		t.Error("TLSState should be 2")
	}
	if len(session.State) != 2 {
		t.Error("State should have 2 bytes")
	}
}
