package cmd

import (
	"context"

	"github.com/spf13/cobra"

	"llm-cli/internal/client"
)

func newRmCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "rm <path>",
		Short: "Remove a file or directory in the VM",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			c := client.New(server)
			return c.DeleteFile(context.Background(), user, args[0])
		},
	}
}
