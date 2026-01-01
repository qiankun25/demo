package config

import (
	"fmt"
	"os"
	"strconv"

	"github.com/go-redis/redis/v8"
	"github.com/minio/minio-go/v7"
	"github.com/minio/minio-go/v7/pkg/credentials"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

type Config struct {
	// Server
	Port int
	Env  string

	// Database
	DBHost     string
	DBPort     int
	DBName     string
	DBUser     string
	DBPassword string

	// Redis
	RedisHost string
	RedisPort int
	RedisDB   int

	// MinIO
	MinIOEndpoint  string
	MinIOAccessKey string
	MinIOSecretKey string
	MinIOBucket    string
	MinIOSecure    bool

	// Translation Engines
	SiliconFlowAPIKey  string
	SiliconFlowAPIBase string
	SiliconFlowModel   string
	DashScopeAPIKey    string
	DashScopeModel     string
	BaiduAppID         string
	BaiduSecretKey     string

	// JWT
	JWTSecret string
}

func Load() *Config {
	return &Config{
		Port:        getEnvInt("PORT", 8002),
		Env:         getEnv("ENV", "development"),
		DBHost:      getEnv("DB_HOST", "localhost"),
		DBPort:       getEnvInt("DB_PORT", 5432),
		DBName:       getEnv("DB_NAME", "translator"),
		DBUser:       getEnv("DB_USER", "translator_user"),
		DBPassword:   getEnv("DB_PASSWORD", ""),
		RedisHost:    getEnv("REDIS_HOST", "localhost"),
		RedisPort:    getEnvInt("REDIS_PORT", 6379),
		RedisDB:      getEnvInt("REDIS_DB", 0),
		MinIOEndpoint: getEnv("MINIO_ENDPOINT", "localhost:9000"),
		MinIOAccessKey: getEnv("MINIO_ACCESS_KEY", "minioadmin"),
		MinIOSecretKey: getEnv("MINIO_SECRET_KEY", "minioadmin"),
		MinIOBucket:    getEnv("MINIO_BUCKET", "papers"),
		MinIOSecure:    getEnvBool("MINIO_SECURE", false),
		SiliconFlowAPIKey:  getEnv("SILICONFLOW_API_KEY", ""),
		SiliconFlowAPIBase: getEnv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn/v1/chat/completions"),
		SiliconFlowModel:   getEnv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3"),
		DashScopeAPIKey:    getEnv("DASHSCOPE_API_KEY", ""),
		DashScopeModel:     getEnv("DASHSCOPE_MODEL", "qwen-plus"),
		BaiduAppID:         getEnv("BAIDU_APP_ID", ""),
		BaiduSecretKey:     getEnv("BAIDU_SECRET_KEY", ""),
		JWTSecret:          getEnv("JWT_SECRET", "your-secret-key-change-in-production"),
	}
}

func InitDB(cfg *Config) (*gorm.DB, error) {
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable",
		cfg.DBHost, cfg.DBPort, cfg.DBUser, cfg.DBPassword, cfg.DBName)

	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	return db, nil
}

func InitRedis(cfg *Config) (*redis.Client, error) {
	client := redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		DB:       cfg.RedisDB,
		Password: "",
	})

	return client, nil
}

func InitMinIO(cfg *Config) (*minio.Client, error) {
	client, err := minio.New(cfg.MinIOEndpoint, &minio.Options{
		Creds:  credentials.NewStaticV4(cfg.MinIOAccessKey, cfg.MinIOSecretKey, ""),
		Secure: cfg.MinIOSecure,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create MinIO client: %w", err)
	}

	return client, nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvBool(key string, defaultValue bool) bool {
	if value := os.Getenv(key); value != "" {
		if boolValue, err := strconv.ParseBool(value); err == nil {
			return boolValue
		}
	}
	return defaultValue
}

