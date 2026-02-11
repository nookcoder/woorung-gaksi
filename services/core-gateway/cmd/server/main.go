package main

import (
	"log"
	"os"

	"time"

	"github.com/gin-gonic/gin"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/config"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/agent"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/auth"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/chat"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/health"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/middleware"
)

func main() {
	// 0. Load Config
	env := os.Getenv("APP_ENV")
	cfg, err := config.Load(env)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	// 1. Setup
	if cfg.Server.Mode == "release" {
		gin.SetMode(gin.ReleaseMode)
	}
	r := gin.Default()

	// 2. Services & Middleware
	jwtService := auth.NewJWTService(cfg.JWT.Secret, 24*time.Hour)
	authMiddleware := middleware.AuthMiddleware(jwtService)
	
	// Dev UX: Print a valid token for testing
	if cfg.Server.Mode == "debug" {
		devToken, _ := jwtService.GenerateToken("dev_admin", "admin")
		log.Printf("\n🔑 [DEV MODE] Access Token: %s\n", devToken)
	}

	// 2.1 Telegram Bot (Optional)
	if cfg.Telegram.Token != "" {
		botService, err := chat.NewBotService(cfg.Telegram.Token, cfg.Server.Mode == "debug")
		if err != nil {
			log.Printf("Failed to init Telegram Bot: %v", err)
		} else {
			chatHandler := chat.NewHandler(botService)
			chatHandler.StartPolling()
		}
	} else {
		log.Println("Telegram Token not found, skipping bot init.")
	}

	// 3. Handlers
	healthHandler := health.NewHealthHandler()
	agentHandler := agent.NewHandler(cfg.PMAgent.URL)

	// 4. Routes
	// Public
	r.GET("/health", healthHandler.Check)
	r.GET("/", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"service": "Woorung-Gaksi Core Gateway",
			"env":     env,
			"status":  "running",
		})
	})

	// Protected API
	api := r.Group("/api/v1")
	api.Use(authMiddleware)
	{
		api.GET("/me", func(c *gin.Context) {
			userID, _ := c.Get("userID")
			role, _ := c.Get("role")
			c.JSON(200, gin.H{"user_id": userID, "role": role})
		})
		api.POST("/ask", agentHandler.Ask)
	}

	// 4. Run
	addr := ":" + cfg.Server.Port
	log.Printf("Starting Core Gateway on %s (env: %s)", addr, env)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to run server: %v", err)
	}
}
