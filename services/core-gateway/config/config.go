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

	log.Printf("Loaded configuration for env: %s", env)
	return &cfg, nil
}
