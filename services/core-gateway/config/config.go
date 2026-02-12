package config

import (
	"log"
	"os"
	"path/filepath"

	"github.com/goccy/go-yaml"
)

type Config struct {
	Server struct {
		Port string `yaml:"port"`
		Mode string `yaml:"mode"`
	} `yaml:"server"`
	DB struct {
		Host     string `yaml:"host"`
		Port     string `yaml:"port"`
		User     string `yaml:"user"`
		Password string `yaml:"password"`
		Name     string `yaml:"name"`
	} `yaml:"db"`
	JWT struct {
		Secret string `yaml:"secret"`
	} `yaml:"jwt"`
	Telegram struct {
		Token string `yaml:"token"`
	} `yaml:"telegram"`
	PMAgent struct {
		URL string `yaml:"url"`
	} `yaml:"pm_agent"`
}

func Load(env string) (*Config, error) {
	if env == "" {
		env = "local"
	}

	configPath := filepath.Join("config", "envs", env+".yaml")
	
	// Open file
	f, err := os.Open(configPath)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	// Decode YAML
	var cfg Config
	decoder := yaml.NewDecoder(f)
	if err := decoder.Decode(&cfg); err != nil {
		return nil, err
	}
	
	// Override with Environment Variables (Docker Support)
	if url := os.Getenv("PM_AGENT_URL"); url != "" {
		cfg.PMAgent.URL = url
	}
	if secret := os.Getenv("API_SECRET"); secret != "" {
		cfg.JWT.Secret = secret
	}
	if token := os.Getenv("TELEGRAM_TOKEN"); token != "" {
		cfg.Telegram.Token = token
	}
	if allowed := os.Getenv("TELEGRAM_ALLOWED_ID"); allowed != "" {
		// Just for consistency, though main.go handles this separately
		// cfg.Telegram.AllowedID = ... (struct doesn't have it yet, skip)
	}

	// Database Overrides
	if host := os.Getenv("DB_HOST"); host != "" {
		cfg.DB.Host = host
	}
	if port := os.Getenv("DB_PORT"); port != "" {
		cfg.DB.Port = port
	}
	if user := os.Getenv("DB_USER"); user != "" {
		cfg.DB.User = user
	}
	if password := os.Getenv("DB_PASSWORD"); password != "" {
		cfg.DB.Password = password
	}
	if name := os.Getenv("DB_NAME"); name != "" {
		cfg.DB.Name = name
	}

	log.Printf("Loaded configuration for env: %s", env)
	return &cfg, nil
}
