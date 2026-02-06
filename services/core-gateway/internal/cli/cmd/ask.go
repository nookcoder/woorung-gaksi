package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

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

	// TODO: Get Token from local storage (or pass via flag for now)
	token := "YOUR_DEV_TOKEN" 

	payload := map[string]string{
		"message": message,
		"source":  "cli",
	}
	jsonData, _ := json.Marshal(payload)

	req, _ := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	if token != "YOUR_DEV_TOKEN" {
		req.Header.Set("Authorization", "Bearer "+token)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		fmt.Printf("Error sending request: %v\n", err)
		return
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	fmt.Printf("[Woorung Reply]: %s\n", string(body))
}
