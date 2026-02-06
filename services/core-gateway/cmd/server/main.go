package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/config"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/health"
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

	// 2. Handlers
	healthHandler := health.NewHealthHandler()

	// 3. Routs
	r.GET("/health", healthHandler.Check)
	r.GET("/", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"service": "Woorung-Gaksi Core Gateway",
			"env":     env,
			"status":  "running",
		})
	})

	// 4. Run
	addr := ":" + cfg.Server.Port
	log.Printf("Starting Core Gateway on %s (env: %s)", addr, env)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Failed to run server: %v", err)
	}
}
