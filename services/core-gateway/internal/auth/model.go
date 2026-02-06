package auth

import "github.com/golang-jwt/jwt/v5"

type Claims struct {
	UserID string `json:"user_id"`
	Role   string `json:"role"`
	jwt.RegisteredClaims
}

type Service interface {
	GenerateToken(userID, role string) (string, error)
	ValidateToken(tokenString string) (*Claims, error)
}
