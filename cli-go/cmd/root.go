package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var (
	server string
	user   string
)

func NewRootCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "llmcli",
		Short: "CLI client for the LLM backend",
	}

	cmd.PersistentFlags().StringVarP(&server, "server", "s", "http://localhost:8000", "API server URL")
	cmd.PersistentFlags().StringVarP(&user, "user", "u", "default", "User name")

	cmd.AddCommand(newChatCmd())
	cmd.AddCommand(newUploadCmd())
	cmd.AddCommand(newLsCmd())
	cmd.AddCommand(newCatCmd())
	cmd.AddCommand(newWriteCmd())
	cmd.AddCommand(newRmCmd())

	return cmd
}

func Execute() {
	if err := NewRootCmd().Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
