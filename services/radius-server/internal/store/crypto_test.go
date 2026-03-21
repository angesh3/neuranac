package store

import (
	"strings"
	"testing"
)

func TestEncryptDecrypt_RoundTrip(t *testing.T) {
	key := "my-secret-key-for-aes-256-test!!"
	plaintext := "super-secret-shared-secret"

	encrypted := encryptValue(plaintext, key)
	if encrypted == plaintext {
		t.Fatal("encrypted value should differ from plaintext")
	}
	if !strings.HasPrefix(encrypted, "enc:") {
		t.Fatalf("encrypted value should start with 'enc:', got: %s", encrypted[:10])
	}

	decrypted := decryptValue(encrypted, key)
	if decrypted != plaintext {
		t.Errorf("decryptValue = %q, want %q", decrypted, plaintext)
	}
}

func TestEncryptDecrypt_EmptyKey(t *testing.T) {
	plaintext := "hello"
	encrypted := encryptValue(plaintext, "")
	if encrypted != plaintext {
		t.Error("empty key should return plaintext unchanged")
	}
	decrypted := decryptValue(plaintext, "")
	if decrypted != plaintext {
		t.Error("empty key decrypt should return value unchanged")
	}
}

func TestEncryptDecrypt_EmptyPlaintext(t *testing.T) {
	encrypted := encryptValue("", "some-key")
	if encrypted != "" {
		t.Error("empty plaintext should return empty string")
	}
}

func TestDecrypt_UnencryptedValue(t *testing.T) {
	// Backward compat: values without "enc:" prefix pass through
	val := "plaintext-secret"
	got := decryptValue(val, "some-key")
	if got != val {
		t.Errorf("decryptValue should pass through unencrypted values, got %q", got)
	}
}

func TestDecrypt_WrongKey(t *testing.T) {
	key1 := "correct-key-32-bytes-long-here!!"
	key2 := "wrong-key-32-bytes-long-here!!!!"

	encrypted := encryptValue("secret", key1)
	decrypted := decryptValue(encrypted, key2)
	// Wrong key should return the encrypted value (graceful failure)
	if decrypted == "secret" {
		t.Error("wrong key should not successfully decrypt")
	}
}

func TestDeriveKey_ShortKey(t *testing.T) {
	key := deriveKey("short")
	if len(key) != 32 {
		t.Errorf("deriveKey should pad to 32 bytes, got %d", len(key))
	}
}

func TestDeriveKey_LongKey(t *testing.T) {
	key := deriveKey("this-is-a-very-long-key-that-exceeds-32-bytes-for-testing")
	if len(key) != 32 {
		t.Errorf("deriveKey should truncate to 32 bytes, got %d", len(key))
	}
}

func TestEncryptDecrypt_DifferentCiphertexts(t *testing.T) {
	key := "my-secret-key-for-aes-256-test!!"
	plaintext := "same-value"

	// Two encryptions of the same value should produce different ciphertexts (random nonce)
	enc1 := encryptValue(plaintext, key)
	enc2 := encryptValue(plaintext, key)
	if enc1 == enc2 {
		t.Error("two encryptions of same value should differ (random nonce)")
	}

	// But both should decrypt to the same value
	if decryptValue(enc1, key) != plaintext {
		t.Error("enc1 failed to decrypt")
	}
	if decryptValue(enc2, key) != plaintext {
		t.Error("enc2 failed to decrypt")
	}
}

func TestMustCacheEncryptionKey_Production(t *testing.T) {
	err := MustCacheEncryptionKey("production", "")
	if err == nil {
		t.Error("should require key in production")
	}

	err = MustCacheEncryptionKey("production", "some-key")
	if err != nil {
		t.Errorf("should not error with key set: %v", err)
	}

	err = MustCacheEncryptionKey("development", "")
	if err != nil {
		t.Errorf("should not require key in development: %v", err)
	}
}

func BenchmarkEncryptValue(b *testing.B) {
	key := "benchmark-key-32-bytes-long!!!!"
	for i := 0; i < b.N; i++ {
		encryptValue("shared-secret-value", key)
	}
}

func BenchmarkDecryptValue(b *testing.B) {
	key := "benchmark-key-32-bytes-long!!!!"
	encrypted := encryptValue("shared-secret-value", key)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		decryptValue(encrypted, key)
	}
}
