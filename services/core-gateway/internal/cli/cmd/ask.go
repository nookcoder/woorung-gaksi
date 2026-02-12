package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

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

func init() {
	rootCmd.AddCommand(askCmd)
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

	payload := map[string]string{
		"message": message,
		"source":  "cli",
	}
	jsonData, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)

	// Debug Info
	// fmt.Printf("DEBUG: Sending POST to %s with Token %s...\n", url, token[:10])

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error sending request: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	
	var prettyJSON bytes.Buffer
	if err := json.Indent(&prettyJSON, body, "", "  "); err == nil {
		fmt.Printf("[Woorung Reply]:\n%s\n", prettyJSON.String())
	} else {
		fmt.Printf("[Woorung Reply]: %s\n", string(body))
	}
}
