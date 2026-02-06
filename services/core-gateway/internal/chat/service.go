package chat

import tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"

type Service interface {
	SendMessage(chatID int64, text string) error
	GetUpdatesChan() tgbotapi.UpdatesChannel
}

type botService struct {
	api *tgbotapi.BotAPI
}

func NewBotService(token string, debug bool) (Service, error) {
	bot, err := tgbotapi.NewBotAPI(token)
	if err != nil {
		return nil, err
	}
	bot.Debug = debug
	return &botService{api: bot}, nil
}

func (s *botService) SendMessage(chatID int64, text string) error {
	msg := tgbotapi.NewMessage(chatID, text)
	_, err := s.api.Send(msg)
	return err
}

func (s *botService) GetUpdatesChan() tgbotapi.UpdatesChannel {
	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60
	return s.api.GetUpdatesChan(u)
}
