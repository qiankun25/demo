package model

import (
	"time"

	"github.com/google/uuid"
	"gorm.io/gorm"
)

// Tenant represents a tenant/organization
type Tenant struct {
	ID        uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	Name      string    `gorm:"not null" json:"name"`
	Plan      string    `gorm:"not null;default:'free'" json:"plan"`
	QuotaJSON string    `gorm:"type:jsonb;default:'{}'" json:"quota_json"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// APIKey represents an API key for authentication
type APIKey struct {
	ID        uuid.UUID  `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	TenantID  uuid.UUID  `gorm:"type:uuid;not null" json:"tenant_id"`
	KeyHash   string     `gorm:"unique;not null" json:"key_hash"`
	Scopes    []string   `gorm:"type:text[];default:'{translate:text,translate:image}'" json:"scopes"`
	CreatedAt time.Time  `json:"created_at"`
	RevokedAt *time.Time `json:"revoked_at,omitempty"`
}

// GlossaryProject represents a glossary project
type GlossaryProject struct {
	ID        uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	TenantID  uuid.UUID `gorm:"type:uuid;not null" json:"tenant_id"`
	Name      string    `gorm:"not null" json:"name"`
	Version   int       `gorm:"default:1" json:"version"`
	CreatedAt time.Time `json:"created_at"`
	UpdatedAt time.Time `json:"updated_at"`
}

// GlossaryTerm represents a term entry in a glossary
type GlossaryTerm struct {
	ID            uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	ProjectID    uuid.UUID `gorm:"type:uuid;not null" json:"project_id"`
	SourceText   string    `gorm:"not null;size:500" json:"source_text"`
	TargetText   string    `gorm:"not null;size:500" json:"target_text"`
	POS           string    `gorm:"size:50" json:"pos"`
	Domain        string    `gorm:"size:100" json:"domain"`
	CaseSensitive bool      `gorm:"default:false" json:"case_sensitive"`
	RegexPattern  string    `gorm:"type:text" json:"regex_pattern"`
	Priority      int       `gorm:"default:0" json:"priority"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// Job represents an async translation job
type Job struct {
	ID          uuid.UUID  `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	TenantID    uuid.UUID  `gorm:"type:uuid;not null" json:"tenant_id"`
	Type        string     `gorm:"not null;size:50" json:"type"` // text, image, pdf, batch
	Status      string     `gorm:"not null;default:'pending';size:50" json:"status"` // pending, processing, completed, failed
	Progress    int        `gorm:"default:0" json:"progress"`
	InputRef    string     `gorm:"type:text" json:"input_ref"`
	OutputRef   string     `gorm:"type:text" json:"output_ref"`
	ErrorMsg    string     `gorm:"type:text" json:"error_msg,omitempty"`
	TraceID     string     `gorm:"size:64" json:"trace_id"`
	CreatedAt   time.Time  `json:"created_at"`
	UpdatedAt   time.Time  `json:"updated_at"`
	CompletedAt *time.Time `json:"completed_at,omitempty"`
}

// TranslationCache represents cached translation results
type TranslationCache struct {
	ID                  uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	ContentHash         string    `gorm:"unique;not null;size:64" json:"content_hash"`
	SourceLang          string    `gorm:"not null;size:10" json:"source_lang"`
	TargetLang          string    `gorm:"not null;size:10" json:"target_lang"`
	GlossaryVersionHash string    `gorm:"size:64" json:"glossary_version_hash"`
	TranslatedText      string    `gorm:"type:text;not null" json:"translated_text"`
	QualityScore        float64   `json:"quality_score"`
	CreatedAt           time.Time `json:"created_at"`
	ExpiresAt           time.Time `json:"expires_at"`
}

// Feedback represents user feedback on translations
type Feedback struct {
	ID              uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	TenantID        uuid.UUID `gorm:"type:uuid;not null" json:"tenant_id"`
	TraceID         string    `gorm:"size:64" json:"trace_id"`
	JobID           *uuid.UUID `gorm:"type:uuid" json:"job_id,omitempty"`
	SourceText      string    `gorm:"type:text;not null" json:"source_text"`
	TranslatedText  string    `gorm:"type:text;not null" json:"translated_text"`
	UserTranslation string    `gorm:"type:text" json:"user_translation"`
	Rating          int       `gorm:"check:rating >= 1 AND rating <= 5" json:"rating"`
	CreatedAt       time.Time `json:"created_at"`
}

// AuditLog represents audit logs
type AuditLog struct {
	ID        uuid.UUID `gorm:"type:uuid;primary_key;default:gen_random_uuid()" json:"id"`
	TenantID  *uuid.UUID `gorm:"type:uuid" json:"tenant_id,omitempty"`
	Actor     string    `gorm:"size:255" json:"actor"`
	Action    string    `gorm:"not null;size:100" json:"action"`
	TraceID   string    `gorm:"size:64" json:"trace_id"`
	Metadata  string    `gorm:"type:jsonb" json:"metadata"`
	CreatedAt time.Time `json:"created_at"`
}

// BeforeCreate hook for UUID generation
func (t *Tenant) BeforeCreate(tx *gorm.DB) error {
	if t.ID == uuid.Nil {
		t.ID = uuid.New()
	}
	return nil
}

func (a *APIKey) BeforeCreate(tx *gorm.DB) error {
	if a.ID == uuid.Nil {
		a.ID = uuid.New()
	}
	return nil
}

func (g *GlossaryProject) BeforeCreate(tx *gorm.DB) error {
	if g.ID == uuid.Nil {
		g.ID = uuid.New()
	}
	return nil
}

func (gt *GlossaryTerm) BeforeCreate(tx *gorm.DB) error {
	if gt.ID == uuid.Nil {
		gt.ID = uuid.New()
	}
	return nil
}

func (j *Job) BeforeCreate(tx *gorm.DB) error {
	if j.ID == uuid.Nil {
		j.ID = uuid.New()
	}
	return nil
}

func (tc *TranslationCache) BeforeCreate(tx *gorm.DB) error {
	if tc.ID == uuid.Nil {
		tc.ID = uuid.New()
	}
	return nil
}

func (f *Feedback) BeforeCreate(tx *gorm.DB) error {
	if f.ID == uuid.Nil {
		f.ID = uuid.New()
	}
	return nil
}

func (a *AuditLog) BeforeCreate(tx *gorm.DB) error {
	if a.ID == uuid.Nil {
		a.ID = uuid.New()
	}
	return nil
}

