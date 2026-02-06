package chat

import (
	"log"
)

type Handler struct {
	service Service
}

func NewHandler(service Service) *Handler {
	return &Handler{service: service}
}

// StartPolling starts a background goroutine to listen for updates
func (h *Handler) StartPolling() {
	updates := h.service.GetUpdatesChan()

	go func() {
		for update := range updates {
			if update.Message == nil {
				continue
			}

			log.Printf("[%s] %s", update.Message.From.UserName, update.Message.Text)

			// Echo Logic (Simple Reply)
			replyText := "Echo from Go Gateway: " + update.Message.Text
			if err := h.service.SendMessage(update.Message.Chat.ID, replyText); err != nil {
				log.Printf("Failed to send message: %v", err)
			}
		}
	}()
	
	log.Println("Telegram Bot Polling Started...")
}
