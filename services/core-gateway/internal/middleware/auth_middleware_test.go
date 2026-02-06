package middleware_test

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/auth"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/middleware"
	"github.com/stretchr/testify/assert"
)

func TestAuthMiddleware(t *testing.T) {
	// Arrange
	gin.SetMode(gin.TestMode)
	jwtService := auth.NewJWTService("secret", time.Hour)
	token, _ := jwtService.GenerateToken("user_123", "admin")

	r := gin.New()
	r.Use(middleware.AuthMiddleware(jwtService))
	
	// Protected Endpoints
	r.GET("/protected", func(c *gin.Context) {
		userID, _ := c.Get("userID")
		role, _ := c.Get("role")
		c.JSON(200, gin.H{"userID": userID, "role": role})
	})

	// Act 1: No Token
	req1, _ := http.NewRequest("GET", "/protected", nil)
	w1 := httptest.NewRecorder()
	r.ServeHTTP(w1, req1)

	// Act 2: Valid Token
	req2, _ := http.NewRequest("GET", "/protected", nil)
	req2.Header.Set("Authorization", "Bearer "+token)
	w2 := httptest.NewRecorder()
	r.ServeHTTP(w2, req2)

	// Assert
	assert.Equal(t, http.StatusUnauthorized, w1.Code, "Should block request without token")
	assert.Equal(t, http.StatusOK, w2.Code, "Should allow request with valid token")
	assert.JSONEq(t, `{"userID":"user_123", "role":"admin"}`, w2.Body.String())
}
