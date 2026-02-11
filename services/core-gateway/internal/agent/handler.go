package agent

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"github.com/gin-gonic/gin"
)

type Handler struct {
	pmAgentURL string
}

func NewHandler(pmAgentURL string) *Handler {
	return &Handler{pmAgentURL: pmAgentURL}
}

type AskRequest struct {
	Message string `json:"message" binding:"required"`
	Source  string `json:"source"`
}

func (h *Handler) Ask(c *gin.Context) {
	var req AskRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	// Forward to PM Agent (Python)
	// In real world, we might want to use a Queue (Redis) for async tasks
	// But for "Chat", let's do synchronous call first for simplicity
	
	// Create payload for Python
	payload := map[string]string{
		"message": req.Message,
		"user_id": c.GetString("userID"), // from AuthMiddleware
	}
	jsonData, _ := json.Marshal(payload)

	resp, err := http.Post(h.pmAgentURL+"/ask", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": "Failed to contact PM Agent"})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		c.JSON(http.StatusBadGateway, gin.H{"error": fmt.Sprintf("PM Agent Error: %d", resp.StatusCode)})
		return
	}

	body, _ := io.ReadAll(resp.Body)
	// Just proxy the JSON response
	c.Data(http.StatusOK, "application/json", body)
}
