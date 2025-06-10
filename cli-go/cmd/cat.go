package cmd

import (
	"context"
	"fmt"

	"github.com/spf13/cobra"

	"llm-cli/internal/client"
)

func newCatCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "cat <path>",
		Short: "Print a file from the VM",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			c := client.New(server)
			content, err := c.ReadFile(context.Background(), user, args[0])
			if err != nil {
				return err
			}
			fmt.Print(content)
			return nil
		},
	}
}
