package cmd

import (
	"context"
	"os"

	"github.com/spf13/cobra"

	"llm-cli/internal/client"
)

func newWriteCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "write <path> <file>",
		Short: "Write a local file to a path in the VM",
		Args:  cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			data, err := os.ReadFile(args[1])
			if err != nil {
				return err
			}
			c := client.New(server)
			return c.WriteFile(context.Background(), user, args[0], string(data))
		},
	}
}
