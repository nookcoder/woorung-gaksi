package telegram

import (
	"fmt"
	"log"
	"strconv"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"github.com/nookcoder/woorung-gaksi/services/core-gateway/internal/agent"
)

type Bot struct {
	api     *tgbotapi.BotAPI
	service agent.Service
	allowedChatID int64
}

// NewBot creates a new Telegram Bot instance
func NewBot(token string, allowedChatID int64, service agent.Service) (*Bot, error) {
	api, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		return nil, fmt.Errorf("failed to create bot API: %w", err)
	}

	log.Printf("Authorized on account %s", api.Self.UserName)

	return &Bot{
		api:           api,
		service:       service,
		allowedChatID: allowedChatID,
	}, nil
}

// Start polling for updates
func (b *Bot) Start() {
	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60

	updates := b.api.GetUpdatesChan(u)

	// Process updates in background
	go func() {
		for update := range updates {
			if update.Message == nil { // ignore any non-Message updates
				continue
			}

			// Security Check: Whitelist
			if b.allowedChatID != 0 && update.Message.Chat.ID != b.allowedChatID {
				log.Printf("[Telegram] Unauthorized access attempt from ChatID: %d (User: %s)", update.Message.Chat.ID, update.Message.From.UserName)
				// msg := tgbotapi.NewMessage(update.Message.Chat.ID, "🚫 Access Denied. You are not authorized to use Woorung-Gaksi.")
				// b.api.Send(msg)
				continue
			}

			// Handle message
			go b.handleMessage(update.Message)
		}
	}()
}

func (b *Bot) handleMessage(msg *tgbotapi.Message) {
	log.Printf("[Telegram] Received: %s", msg.Text)

	// Send "Typing..." action
	action := tgbotapi.NewChatAction(msg.Chat.ID, tgbotapi.ChatTyping)
	b.api.Send(action)

	// Use ChatID as ThreadID to maintain persistent conversation for this chat
	threadID := strconv.FormatInt(msg.Chat.ID, 10)
	
	// Create context/timeout if needed in service, but for now just call
	response, _, err := b.service.Ask(msg.Text, "telegram_user", threadID)
	
	if err != nil {
		log.Printf("[Telegram] Error calling agent: %v", err)
		errMsg := tgbotapi.NewMessage(msg.Chat.ID, fmt.Sprintf("⚠️ Error: %v", err))
		b.api.Send(errMsg)
		return
	}

	// Send Response
	reply := tgbotapi.NewMessage(msg.Chat.ID, response)
	
	// Enable Markdown parsing if response contains markdown (Agent usually does)
	// But Telegram MarkdownV2 is strict. Markdown 'legacy' is safer or just text.
	// PM Agent returns Github-style markdown which might conflict with V2.
	// Let's try basic Markdown or just plain text for reliability first.
	// reply.ParseMode = tgbotapi.ModeMarkdown 

	b.api.Send(reply)
}
