package store

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"io"
)

// encryptValue encrypts a plaintext string using AES-256-GCM.
// Returns a base64-encoded ciphertext. If the key is empty, returns plaintext unchanged.
func encryptValue(plaintext, key string) string {
	if key == "" || plaintext == "" {
		return plaintext
	}
	keyBytes := deriveKey(key)
	block, err := aes.NewCipher(keyBytes)
	if err != nil {
		return plaintext // fallback: don't break on misconfiguration
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return plaintext
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return plaintext
	}
	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return "enc:" + base64.StdEncoding.EncodeToString(ciphertext)
}

// decryptValue decrypts a value that was encrypted by encryptValue.
// If the value does not have the "enc:" prefix, it is returned as-is (backward compat).
func decryptValue(encoded, key string) string {
	if key == "" || encoded == "" {
		return encoded
	}
	if len(encoded) < 5 || encoded[:4] != "enc:" {
		return encoded // not encrypted — backward compatible
	}
	data, err := base64.StdEncoding.DecodeString(encoded[4:])
	if err != nil {
		return encoded
	}
	keyBytes := deriveKey(key)
	block, err := aes.NewCipher(keyBytes)
	if err != nil {
		return encoded
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return encoded
	}
	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		return encoded
	}
	nonce, ciphertext := data[:nonceSize], data[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return encoded
	}
	return string(plaintext)
}

// deriveKey pads or truncates the key string to exactly 32 bytes (AES-256).
func deriveKey(key string) []byte {
	b := []byte(key)
	if len(b) >= 32 {
		return b[:32]
	}
	padded := make([]byte, 32)
	copy(padded, b)
	return padded
}

// MustCacheEncryptionKey validates that a cache encryption key is set in production.
func MustCacheEncryptionKey(env, key string) error {
	if env == "production" && key == "" {
		return fmt.Errorf("CACHE_ENCRYPTION_KEY is required in production for encrypting cached secrets")
	}
	return nil
}
