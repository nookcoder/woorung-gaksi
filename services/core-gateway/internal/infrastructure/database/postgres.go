package database

import (
	"fmt"
	"log"

	"github.com/nookcoder/woorung-gaksi/services/core-gateway/config"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

// NewPostgresDB initializes a connection to PostgreSQL using GORM
func NewPostgresDB(cfg config.Config) (*gorm.DB, error) {
	// DSN Format: host=localhost user=gorm password=gorm dbname=gorm port=9920 sslmode=disable TimeZone=Asia/Shanghai
	dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s port=%s sslmode=disable TimeZone=UTC",
		cfg.DB.Host,
		cfg.DB.User,
		cfg.DB.Password,
		cfg.DB.Name,
		cfg.DB.Port,
	)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	log.Println("Connected to PostgreSQL successfully")

	// Get generic SQL DB object for optional configuration (pool settings)
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}

	// SetMaxIdleConns sets the maximum number of connections in the idle connection pool.
	sqlDB.SetMaxIdleConns(10)
	// SetMaxOpenConns sets the maximum number of open connections to the database.
	sqlDB.SetMaxOpenConns(100)
    
	return db, nil
}
