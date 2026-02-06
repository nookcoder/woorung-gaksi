package auth_test

import (
	"testing"
	"time"

	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/auth"
	"github.com/stretchr/testify/assert"
)

func TestJWTService_Cycle(t *testing.T) {
	// Arrange
	secret := "super_secret_key"
	expiry := time.Hour
	service := auth.NewJWTService(secret, expiry)
	userID := "user_123"
	role := "admin"

	// Act 1: Generate
	token, err := service.GenerateToken(userID, role)

	// Assert 1: Should succeed
	assert.NoError(t, err)
	assert.NotEmpty(t, token)

	// Act 2: Validate
	claims, err := service.ValidateToken(token)

	// Assert 2: Should retrieve data
	assert.NoError(t, err)
	assert.NotNil(t, claims)
	assert.Equal(t, userID, claims.UserID)
	assert.Equal(t, role, claims.Role)
	assert.Equal(t, "woorung-gaksi", claims.Issuer)
}

func TestJWTService_InvalidToken(t *testing.T) {
	service := auth.NewJWTService("secret", time.Hour)
	_, err := service.ValidateToken("invalid.token.string")
	assert.Error(t, err)
}
