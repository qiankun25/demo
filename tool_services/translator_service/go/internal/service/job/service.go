package job

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/demo-feature-nexus/translator-service/internal/model"
	"github.com/go-redis/redis/v8"
	"github.com/google/uuid"
	"gorm.io/gorm"
)

// JobService provides job management operations
type JobService interface {
	CreateJob(ctx context.Context, tenantID string, jobType string, inputRef string) (*model.Job, error)
	GetJob(ctx context.Context, jobID string) (*model.Job, error)
	UpdateJobStatus(ctx context.Context, jobID string, status string, progress int) error
	CompleteJob(ctx context.Context, jobID string, outputRef string) error
	FailJob(ctx context.Context, jobID string, errorMsg string) error
	EnqueueJob(ctx context.Context, jobID string) error
	DequeueJob(ctx context.Context) (string, error)
}

type jobService struct {
	db    *gorm.DB
	redis *redis.Client
}

// NewJobService creates a new job service
func NewJobService(db *gorm.DB, redisClient *redis.Client) JobService {
	return &jobService{
		db:    db,
		redis: redisClient,
	}
}

// CreateJob creates a new job
func (s *jobService) CreateJob(ctx context.Context, tenantID string, jobType string, inputRef string) (*model.Job, error) {
	tenantUUID, err := uuid.Parse(tenantID)
	if err != nil {
		return nil, err
	}

	job := &model.Job{
		TenantID: tenantUUID,
		Type:     jobType,
		Status:   "pending",
		Progress: 0,
		InputRef: inputRef,
	}

	if err := s.db.WithContext(ctx).Create(job).Error; err != nil {
		return nil, err
	}

	return job, nil
}

// GetJob retrieves a job by ID
func (s *jobService) GetJob(ctx context.Context, jobID string) (*model.Job, error) {
	var job model.Job
	if err := s.db.WithContext(ctx).First(&job, "id = ?", jobID).Error; err != nil {
		return nil, err
	}
	return &job, nil
}

// UpdateJobStatus updates job status and progress
func (s *jobService) UpdateJobStatus(ctx context.Context, jobID string, status string, progress int) error {
	updates := map[string]interface{}{
		"status":     status,
		"progress":   progress,
		"updated_at": time.Now(),
	}
	return s.db.WithContext(ctx).Model(&model.Job{}).Where("id = ?", jobID).Updates(updates).Error
}

// CompleteJob marks a job as completed
func (s *jobService) CompleteJob(ctx context.Context, jobID string, outputRef string) error {
	now := time.Now()
	updates := map[string]interface{}{
		"status":       "completed",
		"progress":     100,
		"output_ref":   outputRef,
		"completed_at": now,
		"updated_at":    now,
	}
	return s.db.WithContext(ctx).Model(&model.Job{}).Where("id = ?", jobID).Updates(updates).Error
}

// FailJob marks a job as failed
func (s *jobService) FailJob(ctx context.Context, jobID string, errorMsg string) error {
	updates := map[string]interface{}{
		"status":     "failed",
		"error_msg":  errorMsg,
		"updated_at": time.Now(),
	}
	return s.db.WithContext(ctx).Model(&model.Job{}).Where("id = ?", jobID).Updates(updates).Error
}

// EnqueueJob adds a job to the queue
func (s *jobService) EnqueueJob(ctx context.Context, jobID string) error {
	return s.redis.LPush(ctx, "translator:jobs", jobID).Err()
}

// DequeueJob retrieves a job from the queue
func (s *jobService) DequeueJob(ctx context.Context) (string, error) {
	result, err := s.redis.BRPop(ctx, 0, "translator:jobs").Result()
	if err != nil {
		return "", err
	}
	if len(result) < 2 {
		return "", fmt.Errorf("invalid queue result")
	}
	return result[1], nil
}

