package agent

// Service defines the interface for interacting with the PM Agent
type Service interface {
	Ask(message string, userID string, threadID string) (response string, newThreadID string, err error)
}
