package grpc

import (
	"context"
	"strings"

	"github.com/demo-feature-nexus/translator-service/internal/service/translation"
	"google.golang.org/grpc"
)

// TranslatorServer implements the gRPC translator service
// Note: This requires generated code from translator.proto
// Run: make proto to generate the code
type TranslatorServer struct {
	textTranslator  *translation.TextTranslator
	imageTranslator *translation.ImageTranslator
}

// NewTranslatorServer creates a new gRPC server
func NewTranslatorServer(
	textTranslator *translation.TextTranslator,
	imageTranslator *translation.ImageTranslator,
) *TranslatorServer {
	return &TranslatorServer{
		textTranslator:  textTranslator,
		imageTranslator: imageTranslator,
	}
}

// RegisterService registers the service with gRPC server
// This will be implemented after proto code generation
func (s *TranslatorServer) RegisterService(server *grpc.Server) {
	// RegisterTranslatorServiceServer(server, s)
	// Uncomment after running: make proto
}

// Helper function to convert []int to []int32
func int32Slice(slice []int) []int32 {
	result := make([]int32, len(slice))
	for i, v := range slice {
		result[i] = int32(v)
	}
	return result
}

// Helper function to check if string contains substring
func contains(s, substr string) bool {
	return strings.Contains(s, substr)
}
