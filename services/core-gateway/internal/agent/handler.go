package agent

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
)

// AgentClient implements the Service interface for calling PM Agent
type AgentClient struct {
	pmAgentURL string
}

func NewAgentClient(pmAgentURL string) *AgentClient {
	return &AgentClient{pmAgentURL: pmAgentURL}
}

func (c *AgentClient) Ask(message string, userID string, threadID string) (string, string, error) {
	// Create payload for Python
	payload := map[string]interface{}{
		"message":   message,
		"user_id":   userID,
		"thread_id": threadID,
	}
	jsonData, _ := json.Marshal(payload)

	resp, err := http.Post(c.pmAgentURL+"/ask", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", threadID, fmt.Errorf("failed to contact PM Agent: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", threadID, fmt.Errorf("PM Agent returned error: %d", resp.StatusCode)
	}

	body, _ := io.ReadAll(resp.Body)
	
	// Parse response
	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return "", threadID, fmt.Errorf("failed to parse response: %w", err)
	}

	reply, _ := result["reply"].(string)
	newThreadID, _ := result["thread_id"].(string)
	if newThreadID == "" {
		newThreadID = threadID
	}

	return reply, newThreadID, nil
}


// Handler handles HTTP requests for the agent
type Handler struct {
	service Service
}

func NewHandler(service Service) *Handler {
	return &Handler{service: service}
}

type AskRequest struct {
	Message  string `json:"message" binding:"required"`
	Source   string `json:"source"`
	ThreadID string `json:"thread_id"` // Optional: For conversation persistence
}

func (h *Handler) Ask(c *gin.Context) {
	var req AskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	UserID := c.GetString("userID")
	
	reply, newThreadID, err := h.service.Ask(req.Message, UserID, req.ThreadID)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}

	// Respond with same format as before
	c.JSON(http.StatusOK, gin.H{
		"reply":     reply,
		"thread_id": newThreadID,
	})
}
