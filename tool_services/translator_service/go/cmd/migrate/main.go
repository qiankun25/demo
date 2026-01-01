package main

import (
	"database/sql"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"

	_ "github.com/lib/pq"
)

func main() {
	// Get database connection string from environment
	dsn := fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		getEnv("DB_HOST", "localhost"),
		getEnv("DB_PORT", "5432"),
		getEnv("DB_USER", "translator_user"),
		getEnv("DB_PASSWORD", ""),
		getEnv("DB_NAME", "translator"),
	)

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()

	// Test connection
	if err := db.Ping(); err != nil {
		log.Fatalf("Failed to ping database: %v", err)
	}

	// Find migration files
	migrationDir := getEnv("MIGRATION_DIR", "./migrations")
	files, err := ioutil.ReadDir(migrationDir)
	if err != nil {
		log.Fatalf("Failed to read migration directory: %v", err)
	}

	// Execute migrations in order
	for _, file := range files {
		if file.IsDir() || !strings.HasSuffix(file.Name(), ".sql") {
			continue
		}

		migrationPath := filepath.Join(migrationDir, file.Name())
		sqlBytes, err := ioutil.ReadFile(migrationPath)
		if err != nil {
			log.Fatalf("Failed to read migration file %s: %v", migrationPath, err)
		}

		log.Printf("Executing migration: %s", file.Name())
		if _, err := db.Exec(string(sqlBytes)); err != nil {
			log.Fatalf("Failed to execute migration %s: %v", file.Name(), err)
		}

		log.Printf("Migration %s completed successfully", file.Name())
	}

	log.Println("All migrations completed successfully")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
