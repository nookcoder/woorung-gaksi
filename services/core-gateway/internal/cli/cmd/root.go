package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
	Use:   "woorung",
	Short: "CLI Client for Woorung-Gaksi",
	Long:  "Control your AI Factory from the terminal. Neovim ready.",
	Run: func(cmd *cobra.Command, args []string) {
		// Do Stuff Here
		fmt.Println("Hi! I'm your Woorung-Gaksi CLI. Try 'woorung help'")
	},
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
}
