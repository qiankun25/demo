package cache

import (
	"context"
	"encoding/json"
	"time"

	"github.com/go-redis/redis/v8"
)

// Cache provides caching operations
type Cache interface {
	Get(ctx context.Context, key string) interface{}
	Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error
	Delete(ctx context.Context, key string) error
}

type redisCache struct {
	client *redis.Client
}

// NewCache creates a new cache
func NewCache(client *redis.Client) Cache {
	return &redisCache{client: client}
}

// Get retrieves a value from cache
func (c *redisCache) Get(ctx context.Context, key string) interface{} {
	val, err := c.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return nil
	}
	if err != nil {
		return nil
	}

	var result interface{}
	if err := json.Unmarshal([]byte(val), &result); err != nil {
		return nil
	}
	return result
}

// Set stores a value in cache
func (c *redisCache) Set(ctx context.Context, key string, value interface{}, expiration time.Duration) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return c.client.Set(ctx, key, data, expiration).Err()
}

// Delete removes a value from cache
func (c *redisCache) Delete(ctx context.Context, key string) error {
	return c.client.Del(ctx, key).Err()
}

