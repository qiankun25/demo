package glossary

import (
	"context"

	"github.com/demo-feature-nexus/translator-service/internal/model"
	"github.com/demo-feature-nexus/translator-service/internal/service/translation"
	"github.com/google/uuid"
	"gorm.io/gorm"
)

// GlossaryService provides glossary operations
type GlossaryService interface {
	LoadGlossary(ctx context.Context, projectID string) (translation.Glossary, error)
	CreateProject(ctx context.Context, tenantID string, name string) (*model.GlossaryProject, error)
	AddTerm(ctx context.Context, projectID string, term *model.GlossaryTerm) error
	GetTerms(ctx context.Context, projectID string, query string) ([]*model.GlossaryTerm, error)
	DeleteTerm(ctx context.Context, termID string) error
}

type glossaryService struct {
	db *gorm.DB
}

// NewGlossaryService creates a new glossary service
func NewGlossaryService(db *gorm.DB) GlossaryService {
	return &glossaryService{db: db}
}

// LoadGlossary loads glossary for a project
func (s *glossaryService) LoadGlossary(ctx context.Context, projectID string) (translation.Glossary, error) {
	var terms []model.GlossaryTerm
	if err := s.db.WithContext(ctx).Where("project_id = ?", projectID).Find(&terms).Error; err != nil {
		return translation.Glossary{}, err
	}

	glossaryTerms := make([]translation.Term, len(terms))
	for i, t := range terms {
		glossaryTerms[i] = translation.Term{
			SourceText:    t.SourceText,
			TargetText:    t.TargetText,
			CaseSensitive: t.CaseSensitive,
			RegexPattern:  t.RegexPattern,
			Priority:      t.Priority,
		}
	}

	return translation.Glossary{
		ProjectID: projectID,
		Terms:     glossaryTerms,
	}, nil
}

// CreateProject creates a new glossary project
func (s *glossaryService) CreateProject(ctx context.Context, tenantID string, name string) (*model.GlossaryProject, error) {
	tenantUUID, err := uuid.Parse(tenantID)
	if err != nil {
		return nil, err
	}
	project := &model.GlossaryProject{
		TenantID: tenantUUID,
		Name:     name,
		Version:  1,
	}

	if err := s.db.WithContext(ctx).Create(project).Error; err != nil {
		return nil, err
	}

	return project, nil
}

// AddTerm adds a term to a glossary project
func (s *glossaryService) AddTerm(ctx context.Context, projectID string, term *model.GlossaryTerm) error {
	projectUUID, err := uuid.Parse(projectID)
	if err != nil {
		return err
	}
	term.ProjectID = projectUUID
	return s.db.WithContext(ctx).Create(term).Error
}

// GetTerms retrieves terms from a glossary project
func (s *glossaryService) GetTerms(ctx context.Context, projectID string, query string) ([]*model.GlossaryTerm, error) {
	var terms []*model.GlossaryTerm
	queryBuilder := s.db.WithContext(ctx).Where("project_id = ?", projectID)

	if query != "" {
		queryBuilder = queryBuilder.Where("source_text ILIKE ? OR target_text ILIKE ?", "%"+query+"%", "%"+query+"%")
	}

	if err := queryBuilder.Find(&terms).Error; err != nil {
		return nil, err
	}

	return terms, nil
}

// DeleteTerm deletes a term
func (s *glossaryService) DeleteTerm(ctx context.Context, termID string) error {
	return s.db.WithContext(ctx).Delete(&model.GlossaryTerm{}, "id = ?", termID).Error
}

