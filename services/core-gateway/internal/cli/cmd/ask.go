package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
)

// askCmd represents the ask command
var askCmd = &cobra.Command{
	Use:   "ask [message]",
	Short: "Send a message to the PM Agent",
	Long:  `Send a natural language request to the Woorung-Gaksi system via the Gateway.`,
	Args:  cobra.MinimumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		message := args[0]
		sendRequest(message)
	},
}

// resetCmd clears the current session
var resetCmd = &cobra.Command{
	Use:   "reset",
	Short: "Reset the current conversation session",
	Run: func(cmd *cobra.Command, args []string) {
		sessionFile := getSessionFilePath()
		if err := os.Remove(sessionFile); err != nil && !os.IsNotExist(err) {
			fmt.Printf("Error resetting session: %v\n", err)
		} else {
			fmt.Println("Session reset successfully. A new conversation will start next time.")
		}
	},
}

func init() {
	rootCmd.AddCommand(askCmd)
	rootCmd.AddCommand(resetCmd)
}

func getSessionFilePath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ".woorung_session"
	}
	return filepath.Join(home, ".woorung_session")
}

func loadThreadID() string {
	data, err := os.ReadFile(getSessionFilePath())
	if err != nil {
		return ""
	}
	return string(data)
}

func saveThreadID(threadID string) {
	if threadID == "" {
		return
	}
	os.WriteFile(getSessionFilePath(), []byte(threadID), 0600)
}

func sendRequest(message string) {
	// TODO: Load URL from config or env
	url := "http://localhost:8080/api/v1/ask" 

	token := os.Getenv("WOORUNG_TOKEN")
	if token == "" {
		fmt.Println("Error: WOORUNG_TOKEN environment variable not set.")
		fmt.Println("Tip: Check the Gateway server logs for the [DEV MODE] Access Token.")
		return
	}

	threadID := loadThreadID()

	payload := map[string]string{
		"message":   message,
		"source":    "cli",
		"thread_id": threadID,
	}
	jsonData, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error sending request: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	
	// Parse response to capture thread_id
	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err == nil {
		if tid, ok := result["thread_id"].(string); ok && tid != "" {
			saveThreadID(tid)
			// Optional: Print session ID for debugging
			// fmt.Printf("[Session: %s]\n", tid[:8])
		}
	} else {
		// If fails to parse JSON, just print body string later
	}
	
	var prettyJSON bytes.Buffer
	if err := json.Indent(&prettyJSON, body, "", "  "); err == nil {
		fmt.Printf("[Woorung Reply]:\n%s\n", prettyJSON.String())
	} else {
		fmt.Printf("[Woorung Reply]: %s\n", string(body))
	}
}
